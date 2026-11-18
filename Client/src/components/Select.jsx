export default function Select({ label, value, onChange, options }) {
  return (
    <label className="flex flex-col gap-1 font-mono text-[10px] uppercase tracking-widest text-[var(--muted)]">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-white border border-[var(--line)] text-[var(--ink)] normal-case tracking-normal text-xs px-2 py-1.5 min-w-[110px]"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )
}

