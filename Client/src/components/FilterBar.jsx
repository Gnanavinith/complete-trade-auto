export default function FilterBar({ children, shown, total, onClear, onExport }) {
  return (
    <div className="flex flex-col sm:flex-row sm:flex-wrap items-stretch sm:items-end gap-3 border border-[var(--line)] bg-[var(--paper)] p-3">
      <div className="flex flex-wrap items-end gap-2.5 sm:gap-3">
        {children}
      </div>
      <div className="w-full sm:w-auto sm:ml-auto flex items-center justify-between sm:justify-end gap-2 pt-2 sm:pt-0 border-t sm:border-t-0 border-[var(--line)] font-mono text-[11px] text-[var(--muted)]">
        <span>
          Showing {shown} of {total}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClear}
            className="border border-[var(--line)] bg-white px-2.5 py-1.5 hover:bg-[var(--paper)] active:bg-gray-100 cursor-pointer"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onExport}
            disabled={!shown}
            className="border border-[var(--line)] bg-white px-2.5 py-1.5 hover:bg-[var(--paper)] disabled:opacity-40 active:bg-gray-100 cursor-pointer"
          >
            Export CSV
          </button>
        </div>
      </div>
    </div>
  )
}
