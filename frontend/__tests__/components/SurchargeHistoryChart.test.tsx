import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { ReactElement, ReactNode } from 'react';
import { SurchargeHistoryChart } from '@/components/dashboard/SurchargeHistoryChart';
import { ConversationsProvider } from '@/hooks/useConversations';
import { server } from '../mocks/server';

// jsdom has no ResizeObserver; clone-element shim gives the inner BarChart real
// width/height so it actually emits SVG paths. (Same reason as FuelPriceChart.)
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  const React = await import('react');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement }) =>
      React.cloneElement(children, { width: 600, height: 300 } as Record<
        string,
        unknown
      >),
  };
});

// Phase 8 D-02: SurchargeHistoryChart reads useConversations() which now requires
// the provider in its tree. Wrap every standalone render so the hook resolves.
function renderWithProvider(ui: ReactNode) {
  return render(<ConversationsProvider>{ui}</ConversationsProvider>);
}

describe('SurchargeHistoryChart (UI-04 surcharge history)', () => {
  it('renders the LOCKED chart title', () => {
    renderWithProvider(<SurchargeHistoryChart />);
    expect(
      screen.getByRole('heading', { name: 'Recent surcharges' }),
    ).toBeInTheDocument();
  });

  it('renders SVG with at least one bar rect when threads have surcharge_result', async () => {
    const { container } = renderWithProvider(<SurchargeHistoryChart />);
    await waitFor(
      () => {
        const svg = container.querySelector('svg');
        expect(svg).not.toBeNull();
        // Recharts emits <path> for the bar shapes (BarChart uses path-based rendering).
        const bars = svg?.querySelectorAll('.recharts-bar-rectangle, path');
        expect(bars && bars.length).toBeGreaterThan(0);
      },
      { timeout: 3000 },
    );
  });

  it('renders the LOCKED empty copy when no thread has surcharge_result', async () => {
    server.use(
      http.get('http://localhost:8000/api/conversations/:id', () =>
        HttpResponse.json({
          thread_id: 't',
          messages: [],
          surcharge_result: null,
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        }),
      ),
    );
    renderWithProvider(<SurchargeHistoryChart />);
    await waitFor(() => {
      expect(
        screen.getByText(
          'No surcharges calculated yet. Ask the chat for a surcharge to populate this chart.',
        ),
      ).toBeInTheDocument();
    });
  });

  it('renders the LOCKED error copy when the conversations list fails', async () => {
    server.use(
      http.get('http://localhost:8000/api/conversations', () =>
        HttpResponse.json({ error: 'boom' }, { status: 500 }),
      ),
    );
    renderWithProvider(<SurchargeHistoryChart />);
    await waitFor(() => {
      expect(
        screen.getByText(
          "Couldn't load surcharge history. Refresh the page to try again.",
        ),
      ).toBeInTheDocument();
    });
  });

  it('source code contains isAnimationActive={false} and fill="#2563eb"', () => {
    const src = readFileSync(
      resolve(process.cwd(), 'components/dashboard/SurchargeHistoryChart.tsx'),
      'utf-8',
    );
    expect(src).toContain('isAnimationActive={false}');
    expect(src).toContain('fill="#2563eb"');
  });
});
