import { useEffect, useRef, memo, useState } from 'react'

const POPULAR_SYMBOLS = [
  { label: 'BTC/USDT (Binance)', value: 'BINANCE:BTCUSDT' },
  { label: 'BTC/USD (Coinbase)', value: 'COINBASE:BTCUSD' },
  { label: 'BTC/USD (Bitstamp)', value: 'BITSTAMP:BTCUSD' },
]

function TradingViewChart({ defaultSymbol = 'BINANCE:BTCUSDT' }) {
  const containerRef = useRef(null)
  const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol)
  const [timeframe, setTimeframe] = useState('15')

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    container.innerHTML = ''

    const widgetContainer = document.createElement('div')
    widgetContainer.className = 'tradingview-widget-container'
    widgetContainer.style.height = '100%'
    widgetContainer.style.width = '100%'

    const widgetDiv = document.createElement('div')
    widgetDiv.className = 'tradingview-widget-container__widget'
    widgetDiv.style.height = '100%'
    widgetDiv.style.width = '100%'
    widgetContainer.appendChild(widgetDiv)

    const script = document.createElement('script')
    script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js'
    script.type = 'text/javascript'
    script.async = true
    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: selectedSymbol,
      interval: timeframe,
      timezone: 'exchange',
      theme: 'light',
      style: '1',
      locale: 'en',
      enable_publishing: false,
      allow_symbol_change: true,
      calendar: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: true,
      studies: [
        'STD;EMA',
        'STD;RSI',
      ],
      support_host: 'https://www.tradingview.com',
    })

    widgetContainer.appendChild(script)
    container.appendChild(widgetContainer)

    return () => {
      if (container) container.innerHTML = ''
    }
  }, [selectedSymbol, timeframe])

  return (
    <div className="bg-white border border-[var(--line)] p-3 sm:p-5 flex flex-col">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--line)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <h2 className="font-display text-base sm:text-lg font-medium">
              TradingView Live Market Chart
            </h2>
          </div>
          <p className="font-mono text-[11px] text-[var(--muted)] mt-0.5">
            Real-time BTC candlesticks, technical indicators &amp; multi-timeframe analysis
          </p>
        </div>

        {/* Quick controls */}
        <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
          <div className="flex items-center border border-[var(--line)] bg-[var(--paper)]">
            {['1', '5', '15', '60', 'D'].map((tf) => (
              <button
                key={tf}
                type="button"
                onClick={() => setTimeframe(tf)}
                className={`px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  timeframe === tf
                    ? 'bg-[var(--ink)] text-white'
                    : 'text-[var(--muted)] hover:text-[var(--ink)]'
                }`}
              >
                {tf === '60' ? '1H' : tf === 'D' ? '1D' : `${tf}m`}
              </button>
            ))}
          </div>

          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-white border border-[var(--line)] text-xs px-2 py-1 font-mono text-[var(--ink)]"
          >
            {POPULAR_SYMBOLS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="relative w-full h-[380px] sm:h-[480px] md:h-[560px] mt-3">
        <div ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  )
}

export default memo(TradingViewChart)

