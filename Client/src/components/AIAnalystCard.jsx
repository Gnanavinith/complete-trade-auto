import { useState, useEffect } from 'react'
import { getAIAnalysis, generateAIAnalysis } from '../Api.jsx'

export default function AIAnalystCard() {
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [broadcasting, setBroadcasting] = useState(false)
  const [msgStatus, setMsgStatus] = useState(null)

  useEffect(() => {
    getAIAnalysis()
      .then((res) => {
        if (res && res.success && res.analysis) setAnalysis(res.analysis)
      })
      .catch(() => null)
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    setMsgStatus(null)
    try {
      const res = await generateAIAnalysis(false)
      if (res && res.success && res.analysis) {
        setAnalysis(res.analysis)
      } else {
        alert('Failed to generate AI analysis: ' + (res?.error || 'Unknown error'))
      }
    } catch (e) {
      alert('Error connecting to AI analyst: ' + String(e))
    } finally {
      setLoading(false)
    }
  }

  const handleSendToInstagram = async () => {
    setBroadcasting(true)
    setMsgStatus(null)
    try {
      const res = await generateAIAnalysis(true)
      if (res && res.success) {
        if (res.analysis) setAnalysis(res.analysis)
        const igDetail = res?.dispatch?.details?.instagram
        const isOk = res?.dispatch?.instagram
        setMsgStatus({
          ok: isOk,
          text: isOk
            ? 'Analysis sent to Instagram successfully!'
            : `Instagram status: ${igDetail || 'Window closed (recipient must DM @tanglome first)'}`,
        })
      } else {
        setMsgStatus({ ok: false, text: 'Dispatch failed: ' + (res?.error || 'Unknown error') })
      }
    } catch (e) {
      setMsgStatus({ ok: false, text: 'Error dispatching message: ' + String(e) })
    } finally {
      setBroadcasting(false)
    }
  }

  const isBull = analysis?.bias?.includes('BULL')
  const isBear = analysis?.bias?.includes('BEAR')

  const badgeClass = isBull
    ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
    : isBear
    ? 'bg-red-100 text-red-800 border-red-300'
    : 'bg-amber-100 text-amber-800 border-amber-300'

  return (
    <div className="bg-white border border-[var(--line)] p-4 sm:p-5 flex flex-col space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[var(--line)]">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 animate-pulse" />
            <h2 className="font-display text-base sm:text-lg font-medium">
              Google Gemini AI Market Intelligence
            </h2>
            <span className="font-mono text-[9px] uppercase tracking-wider bg-slate-100 text-slate-700 px-1.5 py-0.5 border border-slate-200">
              {analysis?.model || 'Gemini 3.1 Flash'}
            </span>
          </div>
          <p className="font-mono text-[11px] text-[var(--muted)] mt-0.5">
            Real-time quantitative strategy evaluation, regime commentary &amp; risk stance
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRefresh}
            disabled={loading || broadcasting}
            className="flex-1 sm:flex-none border border-[var(--line)] bg-[var(--paper)] font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 hover:bg-white active:scale-95 disabled:opacity-50 transition-all cursor-pointer"
          >
            {loading ? 'Analyzing…' : 'Refresh AI Analysis'}
          </button>
          <button
            type="button"
            onClick={handleSendToInstagram}
            disabled={loading || broadcasting}
            className="flex-1 sm:flex-none bg-gradient-to-r from-purple-600 to-pink-600 text-white font-mono text-[11px] uppercase tracking-wider px-3 py-1.5 hover:opacity-95 active:scale-95 disabled:opacity-50 transition-all cursor-pointer shadow-sm"
          >
            {broadcasting ? 'Sending…' : 'Send to Instagram'}
          </button>
        </div>
      </div>

      {msgStatus && (
        <div
          className={`p-2.5 text-xs font-mono border ${
            msgStatus.ok
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300'
              : 'bg-amber-50 text-amber-800 border-amber-300'
          }`}
        >
          {msgStatus.text}
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3 font-mono text-xs">
        <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
          <div className="text-[10px] text-[var(--muted)] uppercase tracking-wider">AI Stance / Bias</div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className={`px-2 py-0.5 border text-xs font-semibold uppercase ${badgeClass}`}>
              {analysis?.bias || 'ANALYZING'}
            </span>
            <span className="text-[11px] text-[var(--muted)]">({analysis?.confidence || '—'})</span>
          </div>
        </div>

        <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
          <div className="text-[10px] text-[var(--muted)] uppercase tracking-wider">Market Regime</div>
          <div className="font-semibold text-sm mt-1">{analysis?.regime || 'TREND'}</div>
        </div>

        <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
          <div className="text-[10px] text-[var(--muted)] uppercase tracking-wider">Key Support</div>
          <div className="font-semibold text-sm text-emerald-700 mt-1">{analysis?.key_support || '—'}</div>
        </div>

        <div className="bg-[var(--paper)] p-3 border border-[var(--line)]">
          <div className="text-[10px] text-[var(--muted)] uppercase tracking-wider">Key Resistance</div>
          <div className="font-semibold text-sm text-red-600 mt-1">{analysis?.key_resistance || '—'}</div>
        </div>
      </div>

      {/* AI Summary Box */}
      <div className="bg-[var(--paper)] border-l-4 border-indigo-500 p-3 sm:p-4 text-xs font-sans">
        <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">
          Executive Takeaway
        </div>
        <div className="text-[13px] leading-relaxed font-medium text-[var(--ink)]">
          "{analysis?.summary || 'Evaluating latest 15m candle close and order book depth…'}"
        </div>
      </div>

      {/* Detailed Insights */}
      {analysis?.insights && analysis.insights.length > 0 && (
        <div className="space-y-1.5 pt-1">
          <div className="font-mono text-[10px] uppercase tracking-wider text-[var(--muted)]">
            Quantitative Bot Insights &amp; Tactical Guidance
          </div>
          <ul className="space-y-1.5 font-sans text-xs text-slate-700">
            {analysis.insights.map((insight, idx) => (
              <li key={idx} className="flex items-start gap-2 bg-white border border-[var(--line)] p-2.5 rounded-none">
                <span className="text-indigo-600 font-bold shrink-0 mt-0.5">•</span>
                <span className="leading-snug">{insight}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {analysis?.iso_time && (
        <div className="text-right font-mono text-[10px] text-[var(--muted)] pt-1">
          Last evaluated: {analysis.iso_time}
        </div>
      )}
    </div>
  )
}

