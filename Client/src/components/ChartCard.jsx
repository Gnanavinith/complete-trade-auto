export default function ChartCard({ title, subtitle, children, empty }) {
  return (
    <div className="bg-white border border-[var(--line)] p-5">
      <div className="mb-3">
        <h3 className="font-display text-base font-medium">{title}</h3>
        {subtitle && (
          <p className="font-mono text-[11px] text-[var(--muted)] mt-0.5">
            {subtitle}
          </p>
        )}
      </div>
      <div className="h-[220px]">
        {empty ? (
          <div className="h-full grid place-items-center font-mono text-xs text-[var(--muted)] text-center px-6">
            {empty}
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  )
}

