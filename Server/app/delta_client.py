"""
Delta Exchange India REST Client with HMAC-SHA256 authentication, retries,
rate-limit handling, dynamic product resolution, and paper mode mock fallback.
"""
import time
import hmac
import hashlib
import json
import logging
import requests
import pandas as pd
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

import urllib3.util.connection as urllib3_cn
urllib3_cn.HAS_IPV6 = False   # force IPv4 only: stops Delta 401 from rotating home IPv6

from app.config import DeltaConfig, config

log = logging.getLogger("delta_client")


class DeltaAPIError(Exception):
    """Custom exception for Delta Exchange API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class DeltaAuthError(DeltaAPIError):
    """Delta API authentication failure (e.g. IP not whitelisted for the API key)."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None, client_ip: Optional[str] = None):
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.client_ip = client_ip


class DeltaClient:
    def __init__(self, cfg: DeltaConfig, paper_mode: bool = True):
        self.cfg = cfg
        self.paper_mode = paper_mode
        self.base_url = cfg.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CompleteTradeAuto-BTCBot/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self._btc_product_id: Optional[int] = None
        self._btc_symbol: str = "BTCUSD"

        # IP-whitelist / auth failure handling
        # -------------------------------------------------------------------
        # On an auth error we halt the engine via on_auth_failure, log the
        # client_ip once, and refuse to retry authenticated calls for a
        # cool-down window so the same error cannot spam the log several
        # times a second.
        self.on_auth_failure = None                      # type: Optional[Callable[[str], None]]
        self._auth_failed = False
        self._auth_fail_time = 0.0
        self._auth_client_ip: Optional[str] = None
        self.AUTH_RETRY_MIN_INTERVAL = 60.0              # seconds between auth retries

    def _generate_signature(self, method: str, path: str, query_string: str = "", payload: str = "", timestamp: str = "") -> str:
        """
        Delta Exchange signature formula:
        signature = HMAC_SHA256(secret, method + timestamp + path + query_string + payload)
        """
        message = method.upper() + timestamp + path + query_string + payload
        signature = hmac.new(
            self.cfg.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, auth: bool = False) -> Any:
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"

        query_string = ""
        if params:
            query_string = "?" + urlencode(params)

        payload_str = ""
        if data is not None:
            payload_str = json.dumps(data, separators=(",", ":"))

        url = f"{self.base_url}{path}"
        if query_string:
            url += query_string

        headers = {}
        if auth:
            if not self.cfg.api_key or not self.cfg.api_secret:
                raise DeltaAPIError("API key and secret required for authenticated requests")
            timestamp = str(int(time.time()))
            signature = self._generate_signature(method, path, query_string, payload_str, timestamp)
            headers.update({
                "api-key": self.cfg.api_key,
                "timestamp": timestamp,
                "signature": signature,
            })

        # If we recently hit an auth failure, skip authenticated retries until
        # the cool-down elapses. This stops the same 401 from looping and
        # guarantees we retry at most once every AUTH_RETRY_MIN_INTERVAL seconds.
        if auth and self._auth_failed:
            elapsed = time.time() - self._auth_fail_time
            if elapsed < self.AUTH_RETRY_MIN_INTERVAL:
                remaining = int(self.AUTH_RETRY_MIN_INTERVAL - elapsed)
                raise DeltaAuthError(
                    f"Delta API auth failed (client_ip={self._auth_client_ip or 'unknown'}). "
                    f"Skipping authenticated request; next retry in {remaining}s.",
                    status_code=401,
                    client_ip=self._auth_client_ip,
                )

        max_retries = 3
        backoff = 1.0

        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    response = self.session.get(url, headers=headers, timeout=10)
                elif method.upper() == "POST":
                    response = self.session.post(url, headers=headers, data=payload_str if payload_str else None, timeout=10)
                elif method.upper() == "DELETE":
                    response = self.session.delete(url, headers=headers, timeout=10)
                elif method.upper() == "PUT":
                    response = self.session.put(url, headers=headers, data=payload_str if payload_str else None, timeout=10)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                if response.status_code == 429:
                    log.warning("Delta rate limit hit (429). Retrying in %ss...", backoff)
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                if response.status_code >= 400:
                    err_msg, err_code, client_ip = self._parse_delta_error(response)

                    is_auth_error = (
                        response.status_code == 401
                        or "ip_not_whitelisted_for_api_key" in f"{err_code} {err_msg}".lower()
                        or ("ip" in err_msg.lower() and "whitelist" in err_msg.lower())
                    )

                    if is_auth_error:
                        now = time.time()
                        # React (halt engine + log) at most once per cool-down window.
                        if not self._auth_failed or (now - self._auth_fail_time) >= self.AUTH_RETRY_MIN_INTERVAL:
                            self._auth_failed = True
                            self._auth_fail_time = now
                            self._auth_client_ip = client_ip
                            ip_str = client_ip or "unknown"
                            log.error(
                                "Delta API auth failed: %s (status=%s, client_ip=%s). "
                                "Engine will be HALTED. Whitelist IP %s on Delta and restart. "
                                "Also confirm DELTA_ENV matches the key (testnet vs production).",
                                err_msg, response.status_code, ip_str, ip_str,
                            )
                            if self.on_auth_failure:
                                try:
                                    self.on_auth_failure(ip_str)
                                except Exception as cb_exc:
                                    log.error("Auth failure callback raised: %s", cb_exc)
                        else:
                            log.debug(
                                "Suppressed repeat Delta auth error (rate-limited): %s (client_ip=%s)",
                                err_msg, client_ip or "unknown",
                            )
                        raise DeltaAuthError(
                            f"Delta API auth error [{response.status_code}]: {err_msg}",
                            status_code=response.status_code,
                            response_body=response.text,
                            client_ip=client_ip,
                        )

                    # Non-auth errors (e.g. 429 handled above, other 4xx/5xx).
                    if "signature" in err_msg.lower() or "expired" in err_msg.lower():
                        log.error("Signature / Timestamp expired error. Check system clock sync: %s", err_msg)
                    raise DeltaAPIError(f"Delta API error [{response.status_code}]: {err_msg}", status_code=response.status_code, response_body=response.text)

                if response.content:
                    res_json = response.json()
                    if isinstance(res_json, dict) and "success" in res_json and not res_json["success"]:
                        raise DeltaAPIError(f"Delta API failed success check: {res_json}", response_body=res_json)
                    return res_json.get("result", res_json)
                return {}

            except requests.exceptions.RequestException as e:
                log.warning("Delta request exception on attempt %d/%d: %s", attempt + 1, max_retries, e)
                if attempt == max_retries - 1:
                    raise DeltaAPIError(f"Delta request failed after {max_retries} attempts: {e}")
                time.sleep(backoff)
                backoff *= 2

    @staticmethod
    def _parse_delta_error(response) -> tuple[str, str, Optional[str]]:
        """Extract (message, code, client_ip) from a Delta error response."""
        try:
            err_json = response.json()
            err_obj = err_json.get("error", {}) if isinstance(err_json, dict) else {}
            if isinstance(err_obj, dict):
                err_code = err_obj.get("code", "") or ""
                err_msg = err_obj.get("message") or err_code or getattr(response, "text", "")
                ctx = err_obj.get("context") if isinstance(err_obj.get("context"), dict) else {}
                root_ctx = err_json.get("context") if isinstance(err_json.get("context"), dict) else {}
                client_ip = (
                    err_obj.get("client_ip")
                    or err_obj.get("ip")
                    or ctx.get("client_ip")
                    or ctx.get("ip")
                    or root_ctx.get("client_ip")
                    or err_json.get("client_ip")
                    or response.headers.get("X-Client-Ip")
                    or response.headers.get("CF-Connecting-IP")
                )
            else:
                err_msg = str(err_json)
                err_code = ""
                client_ip = None

            if not client_ip and hasattr(response, "text") and response.text:
                import re
                match = re.search(r'"client_ip"\s*:\s*"([^"]+)"', response.text)
                if match:
                    client_ip = match.group(1)

            return str(err_msg), str(err_code), client_ip
        except Exception:
            client_ip = None
            if hasattr(response, "text") and response.text:
                import re
                match = re.search(r'"client_ip"\s*:\s*"([^"]+)"', response.text)
                if match:
                    client_ip = match.group(1)
            return getattr(response, "text", ""), "", client_ip

    # --- Public Market Data Endpoints ---

    def get_products(self) -> List[Dict[str, Any]]:
        """Fetch all products from Delta Exchange."""
        res = self._request("GET", "/v2/products")
        if isinstance(res, list):
            return res
        return res.get("result", [])

    def get_btc_product_id(self) -> int:
        """Dynamically fetch and cache BTC perpetual product ID and symbol."""
        if self._btc_product_id is not None:
            return self._btc_product_id

        products = self.get_products()
        for p in products:
            symbol = p.get("symbol", "")
            contract_type = p.get("contract_type", "")
            if symbol in ("BTCUSD", "BTCUSDT") or (p.get("underlying_asset", {}).get("symbol") == "BTC" and contract_type == "perpetual"):
                self._btc_product_id = int(p["id"])
                self._btc_symbol = symbol
                log.info("Discovered BTC product ID: %d (symbol=%s)", self._btc_product_id, symbol)
                return self._btc_product_id

        for p in products:
            if "BTC" in p.get("symbol", "") and "PERP" in p.get("contract_type", "").upper():
                self._btc_product_id = int(p["id"])
                self._btc_symbol = p.get("symbol", "BTCUSD")
                log.info("Fallback discovered BTC product ID: %d (symbol=%s)", self._btc_product_id, self._btc_symbol)
                return self._btc_product_id

        raise DeltaAPIError("Could not dynamically find BTC perpetual product ID from /v2/products")

    def get_ticker(self, symbol: str = "BTCUSD") -> Dict[str, Any]:
        """Fetch ticker for symbol."""
        return self._request("GET", f"/v2/tickers/{symbol}")

    def get_candles(self, symbol: str = "BTCUSD", resolution: str = "15m", limit: int = 200, start: Optional[int] = None, end: Optional[int] = None) -> pd.DataFrame:
        """Fetch historical candles and return as pandas DataFrame."""
        if end is None:
            end = int(time.time())
        if start is None:
            mult = 900  # 15m default
            if resolution == "1h":
                mult = 3600
            elif resolution == "1d":
                mult = 86400
            elif resolution == "1m":
                mult = 60
            start = end - (limit * mult)

        params: Dict[str, Any] = {
            "symbol": symbol,
            "resolution": resolution,
            "start": start,
            "end": end,
        }

        res = self._request("GET", "/v2/history/candles", params=params)
        candles = res if isinstance(res, list) else res.get("candles", res.get("result", []))

        if not candles:
            return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])

        if isinstance(candles[0], dict):
            df = pd.DataFrame(candles)
        else:
            cols = ["time", "open", "high", "low", "close", "volume"]
            df = pd.DataFrame([c[:6] for c in candles], columns=cols)

        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].astype(float)
        if "time" in df.columns:
            df = df.sort_values("time").reset_index(drop=True)

        return df

    def get_l2_orderbook(self, product_id: int) -> Dict[str, Any]:
        """Fetch L2 orderbook for product."""
        return self._request("GET", f"/v2/l2orderbook/{product_id}")

    # --- Authenticated Account & Trading Endpoints ---

    def get_wallet_balances(self) -> List[Dict[str, Any]]:
        """Fetch wallet balances (requires auth)."""
        res = self._request("GET", "/v2/wallet/balances", auth=True)
        if isinstance(res, list):
            return res
        return res.get("balances", res.get("result", []))

    def get_positions(self, product_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch open positions (requires auth)."""
        params = {}
        if product_id:
            params["product_id"] = product_id
        res = self._request("GET", "/v2/positions", params=params, auth=True)
        if isinstance(res, list):
            return res
        return res.get("result", [])

    def set_leverage(self, product_id: int, leverage: int) -> Dict[str, Any]:
        """Set leverage for product."""
        payload = {
            "product_id": product_id,
            "leverage": leverage
        }
        return self._request("POST", "/v2/orders/leverage", data=payload, auth=True)

    def place_order(self, product_id: int, size: int, side: str, order_type: str = "market", limit_price: Optional[float] = None, stop_order_price: Optional[float] = None) -> Dict[str, Any]:
        """Place an order on Delta Exchange."""
        payload: Dict[str, Any] = {
            "product_id": product_id,
            "size": int(size),
            "side": side.lower(),
            "order_type": order_type.lower(),
        }
        if limit_price is not None:
            payload["limit_price"] = str(limit_price)
        if stop_order_price is not None:
            payload["stop_order_price"] = str(stop_order_price)

        return self._request("POST", "/v2/orders", data=payload, auth=True)

    def cancel_order(self, product_id: int, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        payload = {
            "product_id": product_id,
            "order_id": order_id
        }
        return self._request("DELETE", "/v2/orders", data=payload, auth=True)


def make_delta_client(cfg: DeltaConfig) -> DeltaClient:
    return DeltaClient(cfg, paper_mode=config.paper_mode)
