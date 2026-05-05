import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { ReactNode } from 'react';
import { FuelPriceChart } from '@/components/dashboard/FuelPriceChart';
import { server } from '../mocks/server';

// jsdom reports 0px width for ResponsiveContainer's parent, which causes Recharts
// to render an empty SVG. Stub ResponsiveContainer to inject a fixed-size wrapper
// so the inner LineChart actually paths-and-paints in the test environment.
// (RESEARCH §Pitfall 4 / OQ 4 — fixed-pixel heights documented; jsdom width fix is
// the standard test-only counterpart.)
// Stub ResponsiveContainer to clone its single child with explicit width/height
// props. Recharts' ResponsiveContainer does the same in production via a
// ResizeObserver, but jsdom does not implement ResizeObserver, leaving the
// inner LineChart with width=0 and no SVG paths. Cloning bypasses that.
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  const React = await import('react');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      React.cloneElement(children, { width: 600, height: 300 } as Record<
        string,
        unknown
      >),
  };
});

describe('FuelPriceChart (UI-04 fuel)', () => {
  it('renders the LOCKED chart title', async () => {
    const { container } = render(<FuelPriceChart />);
    expect(
      screen.getByRole('heading', { name: 'Diesel price (THB/L)' }),
    ).toBeInTheDocument();
    await waitFor(() => {
      const svgOrCopy = container.querySelector('svg') || container.textContent;
      expect(svgOrCopy).toBeTruthy();
    });
  });

  it('renders an SVG with at least one Line path after data loads (Recharts × React 19 smoke)', async () => {
    const { container } = render(<FuelPriceChart />);
    await waitFor(
      () => {
        const svg = container.querySelector('svg');
        expect(svg).not.toBeNull();
        const paths = svg?.querySelectorAll('path');
        expect(paths && paths.length).toBeGreaterThan(0);
      },
      { timeout: 3000 },
    );
  });

  it('shows the LOCKED error copy on 503', async () => {
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', () =>
        HttpResponse.json({ error: 'csv missing' }, { status: 503 }),
      ),
    );
    render(<FuelPriceChart />);
    await waitFor(() => {
      expect(
        screen.getByText("Couldn't load fuel prices. Refresh the page to try again."),
      ).toBeInTheDocument();
    });
  });

  it('shows the LOCKED empty copy when API returns empty array', async () => {
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', () => HttpResponse.json([])),
    );
    render(<FuelPriceChart />);
    await waitFor(() => {
      expect(screen.getByText('No fuel price history available.')).toBeInTheDocument();
    });
  });

  it('source code contains isAnimationActive={false} (Pitfall 4 mitigation)', () => {
    const src = readFileSync(
      resolve(process.cwd(), 'components/dashboard/FuelPriceChart.tsx'),
      'utf-8',
    );
    expect(src).toContain('isAnimationActive={false}');
    expect(src).toContain('stroke="#2563eb"');
  });
});
