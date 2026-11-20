import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import {
  wsURL,
  getStatus,
  getConfig,
  getSymbols,
  getTrades,
  runBacktest as apiRunBacktest,
  startEngine as apiStartEngine,
  stopEngine as apiStopEngine,
  stopAll as apiStopAll,
  testEntry as apiTestEntry,
} from './Api.jsx'
import ChartCard from './components/ChartCard.jsx'
import Select from './components/Select.jsx'
import FilterBar from './components/FilterBar.jsx'
import TradingViewChart from './components/TradingViewChart.jsx'
import AIAnalystCard from './components/AIAnalystCard.jsx'
import { money, downloadCSV, tapePnl } from './utils/formatters.js'

/* ---------- chart constants ---------- */
const GREEN = '#1A9E63'
const RED = '#DC2626'
const INK = '#1a1a1a'
const GRID = '#e6e3dc'
const AXIS = { fontSize: 10, fontFamily: 'monospace', fill: '#8a8578' }
const TIP = { fontFamily: 'monospace', fontSize: 11, border: '1px solid #e6e3dc', borderRadius: 0 }

/* ---------- app ---------- */
export default function App() {
  const [status, setStatus] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [trades, setTrades] = useState([])
  const [backtest, setBacktest] = useState(null)
  const [wsOk, setWsOk] = useState(false)
  const [err, setErr] = useState(null)
  const [loadingBt, setLoadingBt] = useState(false)
  const [priceHistory, setPriceHistory] = useState([])

  // backtest table filters
  const [btSide, setBtSide] = useState('all')
  const [btResult, setBtResult] = useState('all')
  const [btReason, setBtReason] = useState('all')
  const [btSort, setBtSort] = useState('order')

  // execution tape filters
  const [tStatus, setTStatus] = useState('all')
  const [tSide, setTSide] = useState('all')
  const [tResult, setTResult] = useState('all')
  const [tSearch, setTSearch] = useState('')
  const [tSort, setTSort] = useState('order')

  const fetchAll = useCallback(async () => {
    try {
      const [st, c, s, t] = await Promise.all([
        getStatus().catch(() => null),
        getConfig().catch(() => null),
        getSymbols().catch(() => null),
        getTrades().catch(() => null),
      ])
      if (st) setStatus(st)
      if (c) setCfg(c)
      if (Array.isArray(s)) setSymbols(s)
      if (Array.isArray(t)) setTrades(t)
      setErr(null)
    } catch (e) { setErr(String(e)) }
  }, [])

  useEffect(() => { fetchAll(); const id = setInterval(fetchAll, 5000); return () => clearInterval(id) }, [fetchAll])

  // Websocket connection
  useEffect(() => {
    let ws
    let retry
    const connect = () => {
      try {
        ws = new WebSocket(wsURL())
        ws.onopen = () => setWsOk(true)
        ws.onclose = () => { setWsOk(false); retry = setTimeout(connect, 2500) }
        ws.onerror = () => { try { ws.close() } catch {} }
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data)
            if (msg.type === 'init' && msg.status) setStatus((prev) => ({ ...prev, ...msg.status }))
            else if (msg.type === 'engine_update' && msg.result) fetchAll()
          } catch {}
        }
      } catch { retry = setTimeout(connect, 3000) }
    }
    connect()
    return () => { try { ws && ws.close() } catch {}; clearTimeout(retry) }
  }, [fetchAll])

  const runBacktest = async () => {
    setLoadingBt(true)
    try {
      const res = await apiRunBacktest()
      if (res && res.error) alert('Backtest error: ' + res.error)
      else if (res) setBacktest(res)
      else alert('Failed to receive backtest results.')
    } catch (e) { alert(String(e)) } finally { setLoadingBt(false) }
  }

  const startEngine = async () => {
    try { await apiStartEngine(); fetchAll() } catch (e) { alert(String(e)) }
  }
  const stopEngine = async () => {
    try { await apiStopEngine(); fetchAll() } catch (e) { alert(String(e)) }
  }
  const stopAll = async () => {
    try {
      await apiStopAll()
      fetchAll()
      alert('Kill switch activated. Engine halted.')
    } catch (e) { alert(String(e)) }
  }
  const testEntry = async () => {
    try {
      const data = await apiTestEntry()
      if (data && data.success) { alert('Test Entry Executed Successfully!'); fetchAll() }
      else alert('Test Entry Failed: ' + (data?.error || 'Unknown error'))
    } catch (e) { alert(String(e)) }
  }

  const btcPrice = symbols.find((s) => s.symbol === 'BTCUSD')?.price ?? 65000

  // keep a rolling price history for the live chart (session only)
  useEffect(() => {
    const live = symbols.find((s) => s.symbol === 'BTCUSD')?.price
    if (live === undefined || live === null) return
    setPriceHistory((prev) => {
      const next = [...prev, { t: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }), price: Number(live) }]
      return next.slice(-180)
    })
  }, [symbols])

  /* ---------- backtest derived data ---------- */
  const btTrades = backtest?.trades ?? []

  const btCurve = useMemo(() => {
    if (!btTrades.length) return []
    const start = Number(backtest.final_equity) - Number(backtest.net_pnl)
    let eq = start
    let peak = start
    const out = [{ n: 0, equity: +start.toFixed(2), dd: 0 }]
    btTrades.forEach((t, i) => {
      eq += Number(t.net_pnl || 0)
      peak = Math.max(peak, eq)
      out.push({ n: i + 1, equity: +eq.toFixed(2), dd: +(((eq - peak) / peak) * 100).toFixed(2) })
    })
    return out
  }, [backtest, btTrades])

  const btPnlBars = useMemo(
    () => btTrades.map((t, i) => ({ n: i + 1, pnl: Number(t.net_pnl || 0) })),
    [btTrades]
  )

  const btReasons = useMemo(() => [...new Set(btTrades.map((t) => t.exit_reason).filter(Boolean))], [btTrades])

  const btRows = useMemo(() => {
    let rows = btTrades.map((t, i) => ({ ...t, _i: i + 1 }))
    if (btSide !== 'all') rows = rows.filter((t) => t.side === btSide)
    if (btResult === 'win') rows = rows.filter((t) => Number(t.net_pnl) > 0)
    if (btResult === 'loss') rows = rows.filter((t) => Number(t.net_pnl) <= 0)
    if (btReason !== 'all') rows = rows.filter((t) => t.exit_reason === btReason)
    if (btSort === 'best') rows.sort((a, b) => b.net_pnl - a.net_pnl)
    if (btSort === 'worst') rows.sort((a, b) => a.net_pnl - b.net_pnl)
    if (btSort === 'latest') rows.sort((a, b) => b._i - a._i)
    return rows
  }, [btTrades, btSide, btResult, btReason, btSort])

  const clearBtFilters = () => { setBtSide('all'); setBtResult('all'); setBtReason('all'); setBtSort('order') }

  /* ---------- execution tape derived data ---------- */
  const tStatuses = useMemo(
    () => [...new Set(trades.map((t) => t.status || t.event || 'OPEN'))],
    [trades]
  )

  const tapeRows = useMemo(() => {
    let rows = trades.map((t, i) => ({ ...t, _i: i, _pnl: tapePnl(t), _status: t.status || t.event || 'OPEN' }))
    if (tStatus !== 'all') rows = rows.filter((t) => t._status === tStatus)
    if (tSide !== 'all') rows = rows.filter((t) => String(t.side).toLowerCase() === tSide)
    if (tResult === 'profit') rows = rows.filter((t) => (t._pnl ?? 0) > 0)
    if (tResult === 'loss') rows = rows.filter((t) => (t._pnl ?? 0) < 0)
    if (tSearch.trim()) {
      const q = tSearch.trim().toLowerCase()
      rows = rows.filter((t) => String(t.symbol ?? '').toLowerCase().includes(q))
    }
    if (tSort === 'best') rows.sort((a, b) => (b._pnl ?? -Infinity) - (a._pnl ?? -Infinity))
    if (tSort === 'worst') rows.sort((a, b) => (a._pnl ?? Infinity) - (b._pnl ?? Infinity))
    if (tSort === 'reverse') rows.sort((a, b) => b._i - a._i)
    return rows
  }, [trades, tStatus, tSide, tResult, tSearch, tSort])

  const tapeBars = useMemo(
    () => tapeRows.filter((t) => t._pnl !== null).map((t, i) => ({ n: i + 1, pnl: +t._pnl.toFixed(2) })),
    [tapeRows]
  )

  const clearTapeFilters = () => { setTStatus('all'); setTSide('all'); setTResult('all'); setTSearch(''); setTSort('order') }

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)] font-sans">
      <div className="h-[3px] bg-[var(--brass)]" />
      <header className="bg-white border-b border-[var(--line)] sticky top-0 z-30">
        <div className="max-w-[1420px] mx-auto px-3 sm:px-6 py-2.5 sm:py-0 sm:h-[56px] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5 sm:gap-3">
              <div className="w-7 h-7 bg-[var(--ink)] text-white grid place-items-center font-mono text-[13px] font-medium shrink-0">₿</div>
              <div>
                <div className="font-display text-[15px] sm:text-[17px] font-medium leading-none tracking-tight">Complete Trade Auto</div>
                <div className="font-mono text-[9px] sm:text-[10px] tracking-[0.12em] text-[var(--muted)] uppercase mt-0.5">BTC Perpetual · Delta Exchange India</div>
              </div>
            </div>
            <div className="flex sm:hidden items-center gap-1.5 font-mono text-[10px]">
              <span className={`w-2 h-2 rounded-full animate-pulse border ${wsOk ? 'bg-[#1A9E63]' : 'bg-amber-500'}`} />
              <span className="text-[var(--muted)]">{wsOk ? 'Live' : 'Connecting…'}</span>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <div className="hidden sm:flex items-center gap-2 font-mono text-xs mr-2">
              <span className={`w-2 h-2 rounded-full animate-pulse border ${wsOk ? 'bg-[#1A9E63]' : 'bg-amber-500'}`} />
              <span>{wsOk ? 'Connected' : 'Waking Server…'}</span>
            </div>
            {status?.is_running ? (
              <button onClick={stopEngine} className="flex-1 sm:flex-none text-center bg-amber-600 text-white font-mono text-[10px] sm:text-[11px] tracking-wider uppercase px-2.5 sm:px-4 py-2 hover:bg-amber-700 active:scale-95 transition-all whitespace-nowrap cursor-pointer">STOP ENGINE</button>
            ) : (
              <button onClick={startEngine} className="flex-1 sm:flex-none text-center bg-emerald-600 text-white font-mono text-[10px] sm:text-[11px] tracking-wider uppercase px-2.5 sm:px-4 py-2 hover:bg-emerald-700 active:scale-95 transition-all whitespace-nowrap cursor-pointer">START ENGINE</button>
            )}
            <button onClick={testEntry} className="flex-1 sm:flex-none text-center bg-blue-600 text-white font-mono text-[10px] sm:text-[11px] tracking-wider uppercase px-2.5 sm:px-4 py-2 hover:bg-blue-700 active:scale-95 transition-all whitespace-nowrap cursor-pointer">TEST ENTRY</button>
            <button onClick={stopAll} className="flex-1 sm:flex-none text-center bg-red-600 text-white font-mono text-[10px] sm:text-[11px] tracking-wider uppercase px-2.5 sm:px-4 py-2 hover:bg-red-700 active:scale-95 transition-all whitespace-nowrap cursor-pointer">STOP ALL</button>
          </div>
        </div>
      </header>

      <main className="max-w-[1420px] mx-auto px-3 sm:px-6 py-4 sm:py-6 space-y-4 sm:space-y-6">
        {/* Top Status Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Live Account Balances</div>
            <div className="font-display text-lg mt-1 space-y-1 max-h-20 overflow-y-auto">
              {status?.wallet_balances && status.wallet_balances.length > 0 ? (
                status.wallet_balances.map((b, idx) => (
                  <div key={idx} className="flex justify-between text-xs font-mono">
                    <span>{b.asset_symbol}:</span>
                    <span className="font-medium">${Number(b.balance || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                  </div>
                ))
              ) : (
                <div>${status ? Number(status.equity).toLocaleString(undefined, { minimumFractionDigits: 2 }) : '10,000.00'}</div>
              )}
            </div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">{status?.paper_mode ? 'Paper Mode' : 'Live Delta Exchange'}</div>
          </div>
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Daily PnL vs Cap</div>
            <div className={`font-display text-2xl mt-1 ${(status?.daily_pnl ?? 0) >= 0 ? 'text-[#1A9E63]' : 'text-red-600'}`}>
              {(status?.daily_pnl ?? 0) >= 0 ? '+' : ''}{Number(status?.daily_pnl ?? 0).toFixed(2)} USDT
            </div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">Cap: {cfg?.delta?.daily_loss_cap_pct ?? 3.0}% max loss</div>
          </div>
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Risk Gates & Status</div>
            <div className={`font-mono text-sm font-medium mt-2 px-2 py-1 inline-block ${status?.is_halted ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-800'}`}>
              {status?.is_halted ? `HALTED: ${status.halt_reason}` : (status?.gates_passed ? 'All Gates Passed (Active)' : status?.gate_reason || 'OK')}
            </div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">Consecutive losses: {status?.consecutive_losses ?? 0}</div>
          </div>
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">BTC Perpetual Price</div>
            <div className="font-display text-2xl mt-1">${Number(btcPrice).toLocaleString()}</div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">Symbol: BTCUSD · 15m Candle Engine</div>
          </div>
        </div>

        {/* TradingView Advanced Real-Time Chart */}
        <TradingViewChart defaultSymbol="BINANCE:BTCUSDT" />

        {/* Live charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
          <ChartCard
            title="BTC price (this session)"
            subtitle="Updates every 5 seconds while this page is open"
            empty={priceHistory.length < 2 ? 'Collecting price data. Make sure the server is running.' : null}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={priceHistory} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis dataKey="t" tick={AXIS} minTickGap={40} />
                <YAxis domain={['auto', 'auto']} tick={AXIS} width={70} tickFormatter={(v) => v.toLocaleString()} />
                <Tooltip contentStyle={TIP} formatter={(v) => [money(v), 'Price']} />
                {status?.position?.entry_price && (
                  <ReferenceLine y={Number(status.position.entry_price)} stroke={INK} strokeDasharray="4 4" label={{ value: 'Entry', ...AXIS, position: 'insideTopRight' }} />
                )}
                <Line type="monotone" dataKey="price" stroke={INK} strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="PnL per trade (execution tape)"
            subtitle="Follows the filters on the tape table below"
            empty={tapeBars.length === 0 ? 'No trades with a PnL value yet.' : null}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={tapeBars} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                <XAxis dataKey="n" tick={AXIS} />
                <YAxis tick={AXIS} width={55} />
                <Tooltip contentStyle={TIP} formatter={(v) => [money(v), 'PnL']} labelFormatter={(l) => `Trade ${l}`} />
                <ReferenceLine y={0} stroke={INK} />
                <Bar dataKey="pnl" isAnimationActive={false}>
                  {tapeBars.map((d, i) => <Cell key={i} fill={d.pnl >= 0 ? GREEN : RED} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>

        {/* Google Gemini AI Market Analyst Card */}
        <AIAnalystCard />

        {/* Open Position & Strategy Pipeline Details */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white border border-[var(--line)] p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--line)] pb-3">
              <h2 className="font-display text-lg font-medium">Open Position (Single Bot)</h2>
              <span className="font-mono text-xs text-[var(--muted)]">Source of Truth: Delta Exchange</span>
            </div>
            {!status?.position ? (
              <div className="py-12 text-center font-mono text-xs text-[var(--muted)]">
                No open position. Engine is FLAT, waiting for Trend or Range signal &amp; positive score (&gt;+0.6 or &lt;-0.6).
              </div>
            ) : (
              <div className="space-y-3 font-mono text-xs">
                <div className="flex justify-between bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <span>Side / Size:</span>
                  <b className={status.position.side === 'long' ? 'text-[#1A9E63]' : 'text-red-600'}>{status.position.side.toUpperCase()} ({status.position.size} contracts)</b>
                </div>
                <div className="flex justify-between bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <span>Entry Price:</span>
                  <b>${Number(status.position.entry_price).toLocaleString()}</b>
                </div>
                <div className="flex justify-between bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <span>Liquidation Price:</span>
                  <b>${Number(status.position.liquidation_price).toLocaleString()}</b>
                </div>
                <div className="flex justify-between bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <span>Unrealized PnL:</span>
                  <b className={status.position.unrealized_pnl >= 0 ? 'text-[#1A9E63]' : 'text-red-600'}>${status.position.unrealized_pnl.toFixed(2)}</b>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white border border-[var(--line)] p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-[var(--line)] pb-3">
              <h2 className="font-display text-lg font-medium">Strategy &amp; Decision Pipeline</h2>
              <span className="font-mono text-xs text-[var(--muted)]">Evaluated every 15m closed candle</span>
            </div>
            <div className="space-y-2 font-mono text-xs">
              <div className="p-3 bg-[var(--paper)] border border-[var(--line)] flex justify-between">
                <span>Active Regime:</span>
                <b>TREND / RANGE (ADX &amp; Bollinger Squeeze)</b>
              </div>
              <div className="p-3 bg-[var(--paper)] border border-[var(--line)] flex justify-between">
                <span>Strategies Enabled:</span>
                <b>Trend EMA (9/21) + Range RSI/BB</b>
              </div>
              <div className="p-3 bg-[var(--paper)] border border-[var(--line)] flex justify-between">
                <span>1h Higher-Timeframe Filter:</span>
                <b>Active (EMA 50/200 trend alignment)</b>
              </div>
              <div className="p-3 bg-[var(--paper)] border border-[var(--line)] flex justify-between">
                <span>Risk per Trade:</span>
                <b>{cfg?.delta?.risk_per_trade_pct ?? 0.5}% of Equity (SL = 1.5× ATR)</b>
              </div>
            </div>
          </div>
        </div>

        {/* Backtest Section */}
        <div className="bg-white border border-[var(--line)] p-5 space-y-4">
          <div className="flex justify-between items-center border-b border-[var(--line)] pb-3">
            <div>
              <h2 className="font-display text-lg font-medium">Backtest Results (Walk-Forward Strategy Validation)</h2>
              <p className="font-mono text-xs text-[var(--muted)] mt-0.5">Runs the exact same engine &amp; strategy code path over historical Delta candles with fees &amp; slippage.</p>
            </div>
            <button onClick={runBacktest} disabled={loadingBt} className="bg-[var(--ink)] text-white font-mono text-xs uppercase tracking-widest px-4 py-2 hover:bg-black disabled:opacity-50">
              {loadingBt ? 'Running…' : 'Run Backtest'}
            </button>
          </div>

          {!backtest ? (
            <div className="py-8 text-center font-mono text-xs text-[var(--muted)]">Click "Run Backtest" to evaluate performance metrics on Delta historical data.</div>
          ) : (
            <div className="space-y-5 font-mono text-xs">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Net PnL</div>
                  <div className={`text-base font-medium mt-1 ${backtest.net_pnl >= 0 ? 'text-[#1A9E63]' : 'text-red-600'}`}>${backtest.net_pnl} ({backtest.return_pct}%)</div>
                </div>
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Win Rate</div>
                  <div className="text-base font-medium mt-1">{backtest.win_rate_pct}%</div>
                </div>
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Profit Factor</div>
                  <div className="text-base font-medium mt-1">{backtest.profit_factor}</div>
                </div>
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Total Trades</div>
                  <div className="text-base font-medium mt-1">{backtest.total_trades}</div>
                </div>
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Max Drawdown</div>
                  <div className="text-base font-medium mt-1 text-red-600">{backtest.max_drawdown_pct}%</div>
                </div>
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Final Equity</div>
                  <div className="text-base font-medium mt-1">${backtest.final_equity}</div>
                </div>
              </div>

              {/* Backtest charts */}
              {btTrades.length > 0 && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                  <ChartCard title="Equity curve" subtitle="Account value after each trade">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={btCurve} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                        <XAxis dataKey="n" tick={AXIS} />
                        <YAxis domain={['auto', 'auto']} tick={AXIS} width={60} />
                        <Tooltip contentStyle={TIP} formatter={(v) => [money(v), 'Equity']} labelFormatter={(l) => `After trade ${l}`} />
                        <Area type="monotone" dataKey="equity" stroke={INK} fill={INK} fillOpacity={0.08} strokeWidth={1.5} isAnimationActive={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  <ChartCard title="Drawdown" subtitle="Percent below the previous equity peak">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={btCurve} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                        <XAxis dataKey="n" tick={AXIS} />
                        <YAxis tick={AXIS} width={45} tickFormatter={(v) => `${v}%`} />
                        <Tooltip contentStyle={TIP} formatter={(v) => [`${v}%`, 'Drawdown']} labelFormatter={(l) => `After trade ${l}`} />
                        <Area type="monotone" dataKey="dd" stroke={RED} fill={RED} fillOpacity={0.15} strokeWidth={1.5} isAnimationActive={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  <ChartCard title="PnL per trade" subtitle="Green = win, red = loss">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={btPnlBars} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                        <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
                        <XAxis dataKey="n" tick={AXIS} />
                        <YAxis tick={AXIS} width={50} />
                        <Tooltip contentStyle={TIP} formatter={(v) => [money(v), 'PnL']} labelFormatter={(l) => `Trade ${l}`} />
                        <ReferenceLine y={0} stroke={INK} />
                        <Bar dataKey="pnl" isAnimationActive={false}>
                          {btPnlBars.map((d, i) => <Cell key={i} fill={d.pnl >= 0 ? GREEN : RED} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>
                </div>
              )}

              {/* Backtest trade table with filters */}
              {btTrades.length > 0 && (
                <div className="space-y-3">
                  <FilterBar
                    shown={btRows.length}
                    total={btTrades.length}
                    onClear={clearBtFilters}
                    onExport={() => downloadCSV('backtest-trades.csv', btRows.map(({ _i, ...r }) => ({ trade: _i, ...r })))}
                  >
                    <Select label="Side" value={btSide} onChange={setBtSide} options={[
                      { value: 'all', label: 'All' }, { value: 'long', label: 'Long' }, { value: 'short', label: 'Short' },
                    ]} />
                    <Select label="Result" value={btResult} onChange={setBtResult} options={[
                      { value: 'all', label: 'All' }, { value: 'win', label: 'Wins' }, { value: 'loss', label: 'Losses' },
                    ]} />
                    <Select label="Exit reason" value={btReason} onChange={setBtReason} options={[
                      { value: 'all', label: 'All' }, ...btReasons.map((r) => ({ value: r, label: r })),
                    ]} />
                    <Select label="Sort" value={btSort} onChange={setBtSort} options={[
                      { value: 'order', label: 'Oldest first' }, { value: 'latest', label: 'Latest first' },
                      { value: 'best', label: 'Best PnL' }, { value: 'worst', label: 'Worst PnL' },
                    ]} />
                  </FilterBar>

                  <div className="overflow-x-auto max-h-[360px] overflow-y-auto border border-[var(--line)]">
                    <table className="w-full text-left min-w-[580px]">
                      <thead className="bg-[var(--paper)] border-b border-[var(--line)] text-[var(--muted)] text-[10px] uppercase tracking-widest sticky top-0">
                        <tr><th className="p-2.5">#</th><th className="p-2.5">Side</th><th className="p-2.5">Entry Price</th><th className="p-2.5">Exit Price</th><th className="p-2.5">Exit Reason</th><th className="p-2.5">Net PnL</th></tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--line)]">
                        {btRows.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-[var(--muted)]">No trades match these filters.</td></tr>}
                        {btRows.map((t) => (
                          <tr key={t._i} className="hover:bg-[var(--paper)]">
                            <td className="p-2.5 text-[var(--muted)]">{t._i}</td>
                            <td className="p-2.5"><span className={`px-2 py-0.5 text-[10px] uppercase font-medium ${t.side === 'long' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'}`}>{t.side}</span></td>
                            <td className="p-2.5">${Number(t.entry_price).toLocaleString()}</td>
                            <td className="p-2.5">${Number(t.exit_price).toLocaleString()}</td>
                            <td className="p-2.5">{t.exit_reason}</td>
                            <td className={`p-2.5 font-medium ${t.net_pnl >= 0 ? 'text-[#1A9E63]' : 'text-red-600'}`}>${t.net_pnl.toFixed(2)} ({t.return_pct.toFixed(2)}%)</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Execution Tape */}
        <div className="bg-white border border-[var(--line)] p-5 space-y-3">
          <div className="flex justify-between items-center border-b border-[var(--line)] pb-3">
            <h2 className="font-display text-lg font-medium">Recent Trades &amp; Execution Tape (MongoDB Persisted)</h2>
            <span className="font-mono text-xs text-[var(--muted)]">Live /trades</span>
          </div>

          <FilterBar
            shown={tapeRows.length}
            total={trades.length}
            onClear={clearTapeFilters}
            onExport={() => downloadCSV('execution-tape.csv', tapeRows.map(({ _i, _pnl, _status, ...r }) => ({ status: _status, pnl: _pnl, ...r })))}
          >
            <Select label="Status" value={tStatus} onChange={setTStatus} options={[
              { value: 'all', label: 'All' }, ...tStatuses.map((s) => ({ value: s, label: s })),
            ]} />
            <Select label="Side" value={tSide} onChange={setTSide} options={[
              { value: 'all', label: 'All' }, { value: 'long', label: 'Long' }, { value: 'short', label: 'Short' },
            ]} />
            <Select label="PnL" value={tResult} onChange={setTResult} options={[
              { value: 'all', label: 'All' }, { value: 'profit', label: 'Profit' }, { value: 'loss', label: 'Loss' },
            ]} />
            <label className="flex flex-col gap-1 font-mono text-[10px] uppercase tracking-widest text-[var(--muted)]">
              Symbol
              <input
                value={tSearch}
                onChange={(e) => setTSearch(e.target.value)}
                placeholder="e.g. BTCUSD"
                className="bg-white border border-[var(--line)] text-[var(--ink)] normal-case tracking-normal text-xs px-2 py-1.5 w-[130px]"
              />
            </label>
            <Select label="Sort" value={tSort} onChange={setTSort} options={[
              { value: 'order', label: 'As received' }, { value: 'reverse', label: 'Reversed' },
              { value: 'best', label: 'Best PnL' }, { value: 'worst', label: 'Worst PnL' },
            ]} />
          </FilterBar>

          <div className="overflow-x-auto max-h-[300px] overflow-y-auto font-mono text-xs border border-[var(--line)]">
            <table className="w-full text-left min-w-[620px]">
              <thead className="bg-[var(--paper)] border-b border-[var(--line)] text-[var(--muted)] text-[10px] uppercase tracking-widest sticky top-0">
                <tr>
                  <th className="p-2">Status</th>
                  <th className="p-2">Symbol</th>
                  <th className="p-2">Side</th>
                  <th className="p-2">Entry Price</th>
                  <th className="p-2">Stop Loss</th>
                  <th className="p-2">Take Profit</th>
                  <th className="p-2">Qty</th>
                  <th className="p-2">PnL</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--line)]">
                {trades.length === 0 && <tr><td colSpan={8} className="p-4 text-center text-[var(--muted)]">No trades recorded in MongoDB yet.</td></tr>}
                {trades.length > 0 && tapeRows.length === 0 && <tr><td colSpan={8} className="p-4 text-center text-[var(--muted)]">No trades match these filters.</td></tr>}
                {tapeRows.map((tr) => (
                  <tr key={tr._i} className="hover:bg-[var(--paper)]">
                    <td className="p-2">
                      <span className={`px-1.5 py-0.5 border text-[10px] font-medium ${tr._status === 'CLOSED' ? 'bg-slate-100 text-slate-700 border-slate-300' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
                        {tr._status}
                      </span>
                    </td>
                    <td className="p-2">{tr.symbol}</td>
                    <td className="p-2 font-medium uppercase">{tr.side}</td>
                    <td className="p-2">${Number(tr.entry_price || tr.price || 0).toLocaleString()}</td>
                    <td className="p-2">{tr.stop_loss ? `$${Number(tr.stop_loss).toLocaleString()}` : '-'}</td>
                    <td className="p-2">{tr.take_profit ? `$${Number(tr.take_profit).toLocaleString()}` : '-'}</td>
                    <td className="p-2">{tr.qty} BTC</td>
                    <td className={`p-2 font-medium ${(tr._pnl ?? 0) >= 0 ? 'text-[#1A9E63]' : 'text-red-600'}`}>
                      {tr._pnl !== null ? `$${tr._pnl.toFixed(2)}` : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  )
}