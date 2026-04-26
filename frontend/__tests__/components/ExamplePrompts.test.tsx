import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExamplePrompts } from '@/components/chat/ExamplePrompts';
import { EXAMPLE_PROMPTS } from '@/lib/constants';

describe('ExamplePrompts', () => {
  it('renders all 3 LOCKED prompts', () => {
    render(<ExamplePrompts onClick={() => {}} />);
    for (const p of EXAMPLE_PROMPTS) {
      expect(screen.getByRole('button', { name: p })).toBeInTheDocument();
    }
  });

  it('clicking a prompt calls onClick with that prompt text', async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(<ExamplePrompts onClick={onClick} />);
    await user.click(screen.getByRole('button', { name: EXAMPLE_PROMPTS[0] }));
    expect(onClick).toHaveBeenCalledWith(EXAMPLE_PROMPTS[0]);
  });

  it('renders the LOCKED heading "Try one:"', () => {
    render(<ExamplePrompts onClick={() => {}} />);
    expect(screen.getByText('Try one:')).toBeInTheDocument();
  });

  it('NEVER renders the string "Central Region" (Pitfall 9)', () => {
    const { container } = render(<ExamplePrompts onClick={() => {}} />);
    expect(container.textContent).not.toContain('Central Region');
  });
});
