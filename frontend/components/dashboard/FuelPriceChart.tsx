'use client';
import { useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useFuelPrices } from '@/hooks/useFuelPrices';
import { RangeToggle } from '@/components/dashboard/RangeToggle';
import { DEFAULT_RANGE_DAYS } from '@/lib/constants';

/**
 * UI-04 fuel-price line chart.
 *
 * Locked invariants (UI-SPEC §Copywriting + §Color):
 *  - Chart title: "Diesel price (THB/L)"
 *  - Range toggle labels: 7d | 30d | 90d (default 30d)
 *  - Line stroke: #2563eb (blue-600 — accent reserved-for chart use)
 *  - Empty copy: "No fuel price history available."
 *  - Error copy: "Couldn't load fuel prices. Refresh the page to try again."
 *
 * Pitfalls mitigated:
 *  - Pitfall 3 (Recharts × React 19 blank chart) is mitigated upstream via
 *    package.json overrides.react-is — verified by the SVG-path smoke test.
 *  - Pitfall 4 (animation flicker on re-fetch): isAnimationActive={false} on <Line>.
 */
export function FuelPriceChart() {
  const [days, setDays] = useState<number>(DEFAULT_RANGE_DAYS);
  const { data, loading, error } = useFuelPrices(days);

  return (
    <section className="space-y-3 rounded border border-gray-200 bg-white p-4">
      <header className="flex items-center justify-between">
        <h3 className="text-base font-semibold">Diesel price (THB/L)</h3>
        <RangeToggle selectedDays={days} onChange={setDays} />
      </header>

      {loading && (
        <div
          aria-label="Loading fuel prices"
          className="h-72 w-full animate-pulse rounded bg-gray-50"
        />
      )}

      {!loading && error && (
        <p className="text-sm text-red-600">
          Couldn&apos;t load fuel prices. Refresh the page to try again.
        </p>
      )}

      {!loading && !error && data.length === 0 && (
        <p className="text-sm text-gray-700">No fuel price history available.</p>
      )}

      {!loading && !error && data.length > 0 && (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12 }} unit=" THB" />
            <Tooltip
              formatter={(value) => {
                const n = typeof value === 'number' ? value : Number(value);
                return Number.isFinite(n) ? `${n.toFixed(2)} THB/L` : String(value);
              }}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  );
}
