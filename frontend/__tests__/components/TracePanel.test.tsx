import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TracePanel } from '@/components/trace/TracePanel';
import { HAPPY_TRACE } from '../fixtures/sse';
import { EXAMPLE_PROMPTS } from '@/lib/constants';

describe('TracePanel (D-03 / D-06 / D-09)', () => {
  it('empty + idle renders the LOCKED heading, empty-state body, and 3 example prompts', () => {
    render(
      <TracePanel
        entries={[]}
        isStreaming={false}
        onExamplePromptClick={() => {}}
      />,
    );
    expect(
      screen.getByRole('heading', { name: 'Reasoning trace' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/planner, fuel, route, and pricing/),
    ).toBeInTheDocument();
    for (const p of EXAMPLE_PROMPTS) {
      expect(screen.getByRole('button', { name: p })).toBeInTheDocument();
    }
  });

  it('with entries renders one TraceStep per entry in order', () => {
    render(
      <TracePanel
        entries={HAPPY_TRACE}
        isStreaming={false}
        onExamplePromptClick={() => {}}
      />,
    );
    // 5 trace steps from HAPPY_TRACE
    const steps = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-expanded') !== null);
    expect(steps).toHaveLength(HAPPY_TRACE.length);
  });

  it('while streaming renders the "…thinking" indicator', () => {
    render(
      <TracePanel
        entries={HAPPY_TRACE.slice(0, 2)}
        isStreaming={true}
        onExamplePromptClick={() => {}}
      />,
    );
    expect(screen.getByText('…thinking')).toBeInTheDocument();
  });

  it('clicking an example prompt calls onExamplePromptClick with the prompt text', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <TracePanel
        entries={[]}
        isStreaming={false}
        onExamplePromptClick={onClick}
      />,
    );
    await user.click(screen.getByRole('button', { name: EXAMPLE_PROMPTS[0] }));
    expect(onClick).toHaveBeenCalledWith(EXAMPLE_PROMPTS[0]);
  });
});
