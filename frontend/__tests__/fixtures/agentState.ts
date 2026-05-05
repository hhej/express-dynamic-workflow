import type { ConversationSummary, FuelPricePoint } from '@/types/api.types';

export const SAMPLE_CONVERSATIONS: ConversationSummary[] = [
  {
    thread_id: 'thread-1',
    last_updated: '2026-04-26T09:00:00.000Z',
    first_message_preview: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
  },
  {
    thread_id: 'thread-2',
    last_updated: '2026-04-26T09:30:00.000Z',
    first_message_preview: 'What about Retail Fast?',
  },
];

export const SAMPLE_FUEL_PRICES: FuelPricePoint[] = [
  { date: '2026-04-20', price: 30.1, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-21', price: 30.25, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-22', price: 30.4, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-23', price: 30.5, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-24', price: 30.45, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-25', price: 30.55, unit: 'THB/L', source: 'eppo' },
  { date: '2026-04-26', price: 30.5, unit: 'THB/L', source: 'eppo' },
];
