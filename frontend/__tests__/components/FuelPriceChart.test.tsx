import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { FuelPriceChart } from '@/components/dashboard/FuelPriceChart';
import { server } from '../mocks/server';

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
