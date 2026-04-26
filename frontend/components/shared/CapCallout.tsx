/** D-11 capped callout — yellow-50 banner. Color tokens LOCKED by UI-SPEC §Color. */
export function CapCallout() {
  return (
    <div
      role="alert"
      aria-label="Surcharge capped or floored — review recommended"
      className="flex items-start gap-2 rounded border border-yellow-300 bg-yellow-50 p-3 text-sm text-yellow-900"
    >
      <span aria-hidden>⚠</span>
      <span>Cap/floor applied — review recommended</span>
    </div>
  );
}
