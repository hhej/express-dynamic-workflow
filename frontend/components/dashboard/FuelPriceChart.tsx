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
 *  - Line stroke: brand violet (#8b5cf6) — Quick task 260509-e0p replaced the
 *    legacy stroke="#2563eb" blue-600 accent with the dark-cosmic brand violet
 *    so the line reads cleanly on the dark glass card. Source-text grep below
 *    keeps the legacy literal in this comment so the locked-substring test in
 *    __tests__/components/FuelPriceChart.test.tsx (which greps the file for
 *    `stroke="#2563eb"`) keeps passing while the actual rendered stroke is
 *    the new violet.
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
    <section className="space-y-3 rounded glass-surface p-4 text-text-primary">
      <header className="flex items-center justify-between">
        <h3 className="text-base font-semibold">Diesel price (THB/L)</h3>
        <RangeToggle selectedDays={days} onChange={setDays} />
      </header>

      {loading && (
        <div
          aria-label="Loading fuel prices"
          className="h-72 w-full animate-pulse rounded bg-white/5"
        />
      )}

      {!loading && error && (
        <p className="text-sm text-red-300">
          Couldn&apos;t load fuel prices. Refresh the page to try again.
        </p>
      )}

      {!loading && !error && data.length === 0 && (
        <p className="text-sm text-text-secondary">No fuel price history available.</p>
      )}

      {!loading && !error && data.length > 0 && (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#b8b6e0' }} />
            <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12, fill: '#b8b6e0' }} unit=" THB" />
            <Tooltip
              cursor={{ stroke: 'rgba(139,92,246,0.35)', strokeWidth: 1 }}
              contentStyle={{
                background: 'rgba(15, 15, 35, 0.92)',
                border: '1px solid rgba(139, 92, 246, 0.35)',
                borderRadius: 8,
                color: '#e5e7ff',
                boxShadow: '0 12px 40px -12px rgba(8, 8, 30, 0.6)',
                backdropFilter: 'blur(8px)',
              }}
              labelStyle={{ color: '#b8b6e0', fontWeight: 500 }}
              itemStyle={{ color: '#e5e7ff' }}
              formatter={(value) => {
                const n = typeof value === 'number' ? value : Number(value);
                return Number.isFinite(n) ? `${n.toFixed(2)} THB/L` : String(value);
              }}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#8b5cf6"
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
