import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RangeToggle } from '@/components/dashboard/RangeToggle';

describe('RangeToggle (D-15.1)', () => {
  it('renders 3 LOCKED option labels', () => {
    render(<RangeToggle selectedDays={30} onChange={() => {}} />);
    expect(screen.getByRole('radio', { name: '7d' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '30d' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '90d' })).toBeInTheDocument();
  });

  it('marks the matching button active with bg-blue-600 + text-white', () => {
    render(<RangeToggle selectedDays={7} onChange={() => {}} />);
    const active = screen.getByRole('radio', { name: '7d' });
    expect(active).toHaveAttribute('aria-checked', 'true');
    expect(active.className).toContain('bg-blue-600');
    expect(active.className).toContain('text-white');
    const inactive = screen.getByRole('radio', { name: '30d' });
    expect(inactive).toHaveAttribute('aria-checked', 'false');
    expect(inactive.className).toContain('bg-white');
  });

  it('clicking inactive option calls onChange with its days', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RangeToggle selectedDays={30} onChange={onChange} />);
    await user.click(screen.getByRole('radio', { name: '90d' }));
    expect(onChange).toHaveBeenCalledWith(90);
  });

  it('clicking the already-active option is a no-op', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RangeToggle selectedDays={30} onChange={onChange} />);
    await user.click(screen.getByRole('radio', { name: '30d' }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
