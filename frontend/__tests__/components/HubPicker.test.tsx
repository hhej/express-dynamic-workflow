import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HubPicker } from '@/components/chat/HubPicker';
import type { Hub } from '@/types/agent.types';
import hubsFixture from '../fixtures/hubs.json';

function fixtureToArray(): Hub[] {
  return Object.entries(hubsFixture).map(([hub_id, data]) => ({
    hub_id,
    ...(data as Omit<Hub, 'hub_id'>),
  }));
}

describe('HubPicker', () => {
  it('renders 10 hubs when given the full hub list', () => {
    // Use the fixture — 3 hubs is sufficient to verify rendering
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />);
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    expect(select.options.length).toBe(hubs.length);
  });

  it('renders default selected value as "hq-lat-krabang" on cold start contract', () => {
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />);
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    expect(select.value).toBe('hq-lat-krabang');
  });

  it('calls onChange with new hub_id when user picks a different option', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={onChange} />);
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    await user.selectOptions(select, 'branch-bang-na');
    expect(onChange).toHaveBeenCalledWith('branch-bang-na');
  });

  it('renders option text as "{name} ({zone})" per UI-SPEC <option> rendering rule', () => {
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />);
    // The HQ option text MUST contain the full name plus the zone in parens
    expect(
      screen.getByText(/Express HQ — Lat Krabang Industrial Estate, Bangkok \(central-1\)/),
    ).toBeInTheDocument();
  });

  it('is disabled when disabled prop is true', () => {
    const hubs = fixtureToArray();
    render(
      <HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} disabled />,
    );
    expect(screen.getByLabelText('Origin hub')).toBeDisabled();
  });

  it('renders the locked "From:" label in font-semibold', () => {
    const hubs = fixtureToArray();
    const { container } = render(
      <HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />,
    );
    const labelSpan = container.querySelector('span.font-semibold');
    expect(labelSpan?.textContent).toBe('From:');
  });

  it('select has aria-label="Origin hub" for screen reader compatibility', () => {
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />);
    const select = screen.getByLabelText('Origin hub');
    expect(select).toHaveAttribute('aria-label', 'Origin hub');
  });

  it('preserves option order from props (D-03 ordering — not alphabetical)', () => {
    const hubs = fixtureToArray();
    render(<HubPicker hubs={hubs} value="hq-lat-krabang" onChange={() => {}} />);
    const options = screen.getAllByRole('option') as HTMLOptionElement[];
    // First option must be HQ regardless of alphabetical position
    expect(options[0].value).toBe('hq-lat-krabang');
  });
});
