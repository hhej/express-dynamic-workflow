import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TraceStep } from '@/components/trace/TraceStep';
import { HAPPY_TRACE } from '../fixtures/sse';

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
});
