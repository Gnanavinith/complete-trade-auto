import { useState, useEffect, useCallback } from 'react'
import { fetchJSON, wsURL, API } from './Api.jsx'

export default function App(){
  const [status, setStatus] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [symbols, setSymbols] = useState([])
  const [trades, setTrades] = useState([])
  const [backtest, setBacktest] = useState(null)
  const [wsOk, setWsOk] = useState(false)
  const [err, setErr] = useState(null)
  const [loadingBt, setLoadingBt] = useState(false)

  const fetchAll = useCallback(async()=>{
    try{
      const [st, c, s, t] = await Promise.all([
        fetchJSON('/status').catch(()=>null),
        fetchJSON('/config').catch(()=>null),
        fetchJSON('/symbols').catch(()=>null),
        fetchJSON('/trades').catch(()=>null),
      ])
      if(st) setStatus(st)
      if(c) setCfg(c)
      if(Array.isArray(s)) setSymbols(s)
      if(Array.isArray(t)) setTrades(t)
      setErr(null)
    }catch(e){ setErr(String(e)) }
  },[])

  useEffect(()=>{ fetchAll(); const id=setInterval(fetchAll, 5000); return ()=>clearInterval(id) },[fetchAll])

  // Websocket connection
  useEffect(()=>{
    let ws
    let retry
    const connect = ()=>{
      try{
        ws = new WebSocket(wsURL())
        ws.onopen = ()=> setWsOk(true)
        ws.onclose = ()=> { setWsOk(false); retry=setTimeout(connect, 2500) }
        ws.onerror = ()=> { try{ws.close()}catch{}}
        ws.onmessage = (ev)=>{
          try{
            const msg = JSON.parse(ev.data)
            if(msg.type==='init' && msg.status) setStatus(prev=>({...prev, ...msg.status}))
            else if(msg.type==='engine_update' && msg.result) fetchAll()
          }catch{}
        }
      }catch{ retry=setTimeout(connect,3000) }
    }
    connect()
    return ()=>{ try{ws&&ws.close()}catch{}; clearTimeout(retry) }
  },[fetchAll])

  const runBacktest = async()=>{
    setLoadingBt(true)
    try{
      const res = await fetchJSON('/backtest')
      if(res && res.error) {
        alert("Backtest error: " + res.error)
      } else if(res) {
        setBacktest(res)
      } else {
        alert("Failed to receive backtest results.")
      }
    }catch(e){ alert(String(e)) } finally{ setLoadingBt(false) }
  }

  const startEngine = async()=>{
    try{
      await fetch(`${API}/start`, {method:'POST'})
      fetchAll()
    }catch(e){ alert(String(e)) }
  }

  const stopEngine = async()=>{
    try{
      await fetch(`${API}/stop`, {method:'POST'})
      fetchAll()
    }catch(e){ alert(String(e)) }
  }

  const stopAll = async()=>{
    try{
      await fetch(`${API}/stop-all`, {method:'POST'})
      fetchAll()
      alert('Kill switch activated. Engine halted.')
    }catch(e){ alert(String(e)) }
  }

  const btcPrice = symbols.find(s=>s.symbol==='BTCUSD')?.price ?? 65000

  return (
    <div className="min-h-screen bg-[var(--paper)] text-[var(--ink)] font-sans">
      <div className="h-[3px] bg-[var(--brass)]" />
      <header className="bg-white border-b border-[var(--line)] sticky top-0 z-30">
        <div className="max-w-[1420px] mx-auto px-4 md:px-6 h-[56px] flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-[var(--ink)] text-white grid place-items-center font-mono text-[13px] font-medium">₿</div>
            <div>
              <div className="font-display text-[17px] font-medium leading-none tracking-tight">Complete Trade Auto</div>
              <div className="font-mono text-[10px] tracking-[0.14em] text-[var(--muted)] uppercase -mt-[2px]">BTC Perpetual · Delta Exchange India</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 font-mono text-xs">
              <span className={`w-2 h-2 rounded-full animate-pulse border ${wsOk?'bg-[#1A9E63]':'bg-red-500'}`} />
              <span>{wsOk?'Connected':'Disconnected'}</span>
            </div>
            {status?.is_running ? (
              <button onClick={stopEngine} className="bg-amber-600 text-white font-mono text-[11px] tracking-widest uppercase px-4 py-2 hover:bg-amber-700 transition-colors">STOP ENGINE</button>
            ) : (
              <button onClick={startEngine} className="bg-emerald-600 text-white font-mono text-[11px] tracking-widest uppercase px-4 py-2 hover:bg-emerald-700 transition-colors">START ENGINE</button>
            )}
            <button onClick={stopAll} className="bg-red-600 text-white font-mono text-[11px] tracking-widest uppercase px-4 py-2 hover:bg-red-700 transition-colors">STOP ALL</button>
          </div>
        </div>
      </header>

      <main className="max-w-[1420px] mx-auto px-4 md:px-6 py-6 space-y-6">
        {/* Top Status Banner */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Account Equity</div>
            <div className="font-display text-2xl mt-1">${status ? Number(status.equity).toLocaleString(undefined,{minimumFractionDigits:2}) : '10,000.00'}</div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">{status?.paper_mode ? 'Paper Mode (Simulated)' : 'Live Delta Account'}</div>
          </div>
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Daily PnL vs Cap</div>
            <div className={`font-display text-2xl mt-1 ${(status?.daily_pnl??0)>=0?'text-[#1A9E63]':'text-red-600'}`}>
              {(status?.daily_pnl??0)>=0?'+':''}{Number(status?.daily_pnl??0).toFixed(2)} USDT
            </div>
            <div className="font-mono text-[11px] text-[var(--muted)] mt-1">Cap: {cfg?.delta?.daily_loss_cap_pct ?? 3.0}% max loss</div>
          </div>
          <div className="bg-white border border-[var(--line)] p-4">
            <div className="font-mono text-[10px] uppercase text-[var(--muted)] tracking-widest">Risk Gates & Status</div>
            <div className={`font-mono text-sm font-medium mt-2 px-2 py-1 inline-block ${status?.is_halted?'bg-red-100 text-red-700':'bg-emerald-100 text-emerald-800'}`}>
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
                  <b className={status.position.side==='long'?'text-[#1A9E63]':'text-red-600'}>{status.position.side.toUpperCase()} ({status.position.size} contracts)</b>
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
                  <b className={status.position.unrealized_pnl>=0?'text-[#1A9E63]':'text-red-600'}>${status.position.unrealized_pnl.toFixed(2)}</b>
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
            <div className="space-y-4 font-mono text-xs">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
                  <div className="text-[var(--muted)] uppercase">Net PnL</div>
                  <div className={`text-base font-medium mt-1 ${backtest.net_pnl>=0?'text-[#1A9E63]':'text-red-600'}`}>${backtest.net_pnl} ({backtest.return_pct}%)</div>
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

              {backtest.trades && backtest.trades.length > 0 && (
                <div className="overflow-x-auto border border-[var(--line)]">
                  <table className="w-full text-left">
                    <thead className="bg-[var(--paper)] border-b border-[var(--line)] text-[var(--muted)] text-[10px] uppercase tracking-widest">
                      <tr><th className="p-2.5">Side</th><th className="p-2.5">Entry Price</th><th className="p-2.5">Exit Price</th><th className="p-2.5">Exit Reason</th><th className="p-2.5">Net PnL</th></tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--line)]">
                      {backtest.trades.map((t, idx)=>(
                        <tr key={idx} className="hover:bg-[var(--paper)]">
                          <td className="p-2.5"><span className={`px-2 py-0.5 text-[10px] uppercase font-medium ${t.side==='long'?'bg-emerald-100 text-emerald-800':'bg-red-100 text-red-800'}`}>{t.side}</span></td>
                          <td className="p-2.5">${Number(t.entry_price).toLocaleString()}</td>
                          <td className="p-2.5">${Number(t.exit_price).toLocaleString()}</td>
                          <td className="p-2.5">{t.exit_reason}</td>
                          <td className={`p-2.5 font-medium ${t.net_pnl>=0?'text-[#1A9E63]':'text-red-600'}`}>${t.net_pnl.toFixed(2)} ({t.return_pct.toFixed(2)}%)</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
          <div className="overflow-x-auto max-h-[300px] overflow-y-auto font-mono text-xs">
            <table className="w-full text-left">
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
                {trades.length===0 && <tr><td colSpan={8} className="p-4 text-center text-[var(--muted)]">No trades recorded in MongoDB yet.</td></tr>}
                {trades.map((tr, i)=>(
                  <tr key={i} className="hover:bg-[var(--paper)]">
                    <td className="p-2">
                      <span className={`px-1.5 py-0.5 border text-[10px] font-medium ${tr.status==='CLOSED'?'bg-slate-100 text-slate-700 border-slate-300':'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
                        {tr.status || tr.event || 'OPEN'}
                      </span>
                    </td>
                    <td className="p-2">{tr.symbol}</td>
                    <td className="p-2 font-medium uppercase">{tr.side}</td>
                    <td className="p-2">${Number(tr.entry_price || tr.price || 0).toLocaleString()}</td>
                    <td className="p-2">{tr.stop_loss ? `$${Number(tr.stop_loss).toLocaleString()}` : '-'}</td>
                    <td className="p-2">{tr.take_profit ? `$${Number(tr.take_profit).toLocaleString()}` : '-'}</td>
                    <td className="p-2">{tr.qty} BTC</td>
                    <td className={`p-2 font-medium ${(tr.unrealized_pnl||0)>=0?'text-[#1A9E63]':'text-red-600'}`}>
                      {tr.unrealized_pnl !== undefined ? `$${Number(tr.unrealized_pnl).toFixed(2)}` : '-'}
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
