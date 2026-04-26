'use client';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useConversations } from '@/hooks/useConversations';
import { useSurchargeHistory } from '@/hooks/useSurchargeHistory';

/**
 * UI-04 surcharge-history bar chart, D-15.2 client-side derivation —
 * no new backend endpoint. Walks `useConversations().items` and reads each
 * thread's `surcharge_result` via `useSurchargeHistory`.
 *
 * Locked invariants (UI-SPEC §Copywriting + §Color):
 *  - Chart title: "Recent surcharges"
 *  - Bar fill: #2563eb (blue-600 — accent reserved-for chart use)
 *  - Empty copy: "No surcharges calculated yet. Ask the chat for a surcharge to populate this chart."
 *  - Error copy: "Couldn't load surcharge history. Refresh the page to try again."
 *
 * Pitfall 4 (animation flicker): isAnimationActive={false} on <Bar>.
 * Pitfall 8 (N+1 fetches): mitigated inside useSurchargeHistory via Promise.all.
 */
export function SurchargeHistoryChart() {
  const { items, loading: convLoading, error: convError } = useConversations();
  const {
    data,
    loading: historyLoading,
    error: historyError,
  } = useSurchargeHistory(items, convLoading);

  const loading = convLoading || historyLoading;
  const error = convError || historyError;

  return (
    <section className="space-y-3 rounded border border-gray-200 bg-white p-4">
      <h3 className="text-base font-semibold">Recent surcharges</h3>

      {loading && (
        <div
          aria-label="Loading surcharge history"
          className="h-72 w-full animate-pulse rounded bg-gray-50"
        />
      )}

      {!loading && error && (
        <p className="text-sm text-red-600">
          Couldn&apos;t load surcharge history. Refresh the page to try again.
        </p>
      )}

      {!loading && !error && data.length === 0 && (
        <p className="text-sm text-gray-700">
          No surcharges calculated yet. Ask the chat for a surcharge to populate this
          chart.
        </p>
      )}

      {!loading && !error && data.length > 0 && (
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11 }}
              interval={0}
              angle={-20}
              textAnchor="end"
              height={60}
            />
            <YAxis tick={{ fontSize: 12 }} unit=" THB" />
            <Tooltip
              formatter={(value, name) => {
                const n = typeof value === 'number' ? value : Number(value);
                if (name === 'total' && Number.isFinite(n)) {
                  return [`${n.toFixed(2)} THB`, 'Total'];
                }
                return [String(value), String(name)];
              }}
            />
            <Bar dataKey="total" fill="#2563eb" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
