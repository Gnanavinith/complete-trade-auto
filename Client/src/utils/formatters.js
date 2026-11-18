export const money = (v) =>
  `$${Number(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`

export function downloadCSV(filename, rows) {
  if (!rows || !rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const csv = [
    cols.join(','),
    ...rows.map((r) => cols.map((c) => esc(r[c])).join(',')),
  ].join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const tapePnl = (tr) => {
  const v = tr.pnl ?? tr.net_pnl ?? tr.unrealized_pnl
  return v === undefined || v === null ? null : Number(v)
}

