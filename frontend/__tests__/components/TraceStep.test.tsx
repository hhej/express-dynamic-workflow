import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TraceStep } from '@/components/trace/TraceStep';
import { HAPPY_TRACE } from '../fixtures/sse';
import type { AgentName, TraceEntry } from '@/types/agent.types';

const AGENT_NAMES: readonly AgentName[] = [
  'planner',
  'fuel_agent',
  'route_agent',
  'pricing_agent',
  'response',
  'hitl_gate',
  'search_agent',
] as const;

describe('TraceStep (D-07)', () => {
  it('renders agent label, step counter, reasoning, and status badge collapsed', () => {
    render(<TraceStep entry={HAPPY_TRACE[1]} />);
    expect(screen.getByText('Fuel agent')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
    expect(screen.getByText(/Diesel up 1.87% vs baseline/)).toBeInTheDocument();
    expect(screen.getByText('ok')).toBeInTheDocument();
    // Tool/Input/Output labels NOT visible until expanded
    expect(screen.queryByText('Tool:')).toBeNull();
  });

  it('clicking toggles aria-expanded and reveals Tool / Input / Output / timestamp', async () => {
    const user = userEvent.setup();
    render(<TraceStep entry={HAPPY_TRACE[1]} />);
    const headline = screen.getByRole('button');
    expect(headline).toHaveAttribute('aria-expanded', 'false');
    await user.click(headline);
    expect(headline).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Tool:')).toBeInTheDocument();
    expect(screen.getByText('Input')).toBeInTheDocument();
    expect(screen.getByText('Output')).toBeInTheDocument();
  });

  it('status badge applies the LOCKED palette for ok/warn/error', () => {
    const { rerender } = render(
      <TraceStep entry={{ ...HAPPY_TRACE[0], status: 'ok' }} />,
    );
    expect(screen.getByText('ok').className).toContain('bg-green-100');
    rerender(<TraceStep entry={{ ...HAPPY_TRACE[0], status: 'warn' }} />);
    expect(screen.getByText('warn').className).toContain('bg-yellow-100');
    rerender(<TraceStep entry={{ ...HAPPY_TRACE[0], status: 'error' }} />);
    expect(screen.getByText('error').className).toContain('bg-red-100');
  });

  it('Enter key on the headline toggles expansion', async () => {
    const user = userEvent.setup();
    render(<TraceStep entry={HAPPY_TRACE[1]} />);
    const headline = screen.getByRole('button');
    headline.focus();
    await user.keyboard('{Enter}');
    expect(headline).toHaveAttribute('aria-expanded', 'true');
  });

  it('renders a non-empty label for every AgentName variant (D-15.1 exhaustive loop)', () => {
    const expectedLabel: Record<AgentName, string> = {
      planner: 'Planner',
      fuel_agent: 'Fuel agent',
      route_agent: 'Route agent',
      pricing_agent: 'Pricing agent',
      response: 'Response',
      hitl_gate: 'Approval gate',
      search_agent: 'Search agent',
    };
    for (const agent of AGENT_NAMES) {
      const entry: TraceEntry = {
        step: 1,
        agent,
        tool: null,
        tool_input: {},
        tool_output: {},
        reasoning: `agent=${agent}`,
        timestamp: '2026-05-03T00:00:00.000Z',
        status: 'ok',
      };
      const { unmount } = render(<TraceStep entry={entry} />);
      const headline = screen.getByRole('button');
      const labelText = headline.textContent ?? '';
      expect(labelText).not.toContain('undefined');
      expect(labelText).toContain(expectedLabel[agent]);
      unmount();
    }
  });
});
