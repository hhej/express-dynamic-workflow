'use client';
import { Component, type ErrorInfo, type ReactNode } from 'react';
import { FuelPriceChart } from '@/components/dashboard/FuelPriceChart';
import { SurchargeHistoryChart } from '@/components/dashboard/SurchargeHistoryChart';

/**
 * Local ErrorBoundary used to wrap each chart so a Recharts render failure
 * (e.g., the React 19 + react-is mismatch escape-hatch from Pitfall 3) does
 * not blank the entire dashboard. Plan 04-03 (Wave 3 sibling) is responsible
 * for the canonical `frontend/components/shared/ErrorBoundary.tsx`; this
 * inline copy keeps the parallel-write boundary clean. The integrator (04-05)
 * may swap to the shared import after both Wave 3 plans merge.
 */
interface ChartErrorBoundaryState {
  hasError: boolean;
}

class ChartErrorBoundary extends Component<
  { children: ReactNode },
  ChartErrorBoundaryState
> {
  state: ChartErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ChartErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Chart render error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <section
          role="alert"
          className="rounded glass-surface border-red-300/30 bg-red-500/10 p-4 text-sm text-red-200"
        >
          Something went wrong rendering this chart. Refresh the page to try again.
        </section>
      );
    }
    return this.props.children;
  }
}

/**
 * D-04 dashboard tab content. Both charts wrap in a local ErrorBoundary so a
 * single chart's render failure cannot cascade to the rest of the app.
 */
export function DashboardView() {
  return (
    <div className="flex flex-col gap-6 overflow-y-auto p-6 text-text-primary">
      <h2 className="text-base font-semibold">Dashboard</h2>
      <ChartErrorBoundary>
        <FuelPriceChart />
      </ChartErrorBoundary>
      <ChartErrorBoundary>
        <SurchargeHistoryChart />
      </ChartErrorBoundary>
    </div>
  );
}
