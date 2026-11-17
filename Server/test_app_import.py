"""
Test FastAPI app import and health endpoint.
Run: python -I test_app_import.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
from fastapi.testclient import TestClient
from app.main import app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("test_import")

def main():
    log.info("Testing FastAPI app startup and health endpoint...")
    client = TestClient(app)
    response = client.get("/health")
    log.info("Health endpoint response: status=%d, json=%s", response.status_code, response.json())
    assert response.status_code == 200

    cfg_resp = client.get("/config")
    log.info("Config endpoint response: status=%d, json=%s", cfg_resp.status_code, cfg_resp.json())
    assert cfg_resp.status_code == 200

    log.info("=== FASTAPI APP IMPORT & ENDPOINT TESTS PASSED ===")

if __name__ == "__main__":
    main()
