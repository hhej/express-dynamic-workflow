import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useFuelPrices } from '@/hooks/useFuelPrices';
import { server } from '../mocks/server';

describe('useFuelPrices', () => {
  it('loads fuel prices via MSW and exposes data on success', async () => {
    const { result } = renderHook(() => useFuelPrices(7));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data.length).toBeGreaterThan(0);
    expect(result.current.error).toBeNull();
  });

  it('changing days re-fetches with the new query param', async () => {
    const seenDays: string[] = [];
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', ({ request }) => {
        const url = new URL(request.url);
        seenDays.push(url.searchParams.get('days') ?? '');
        return HttpResponse.json([]);
      }),
    );
    const { result, rerender } = renderHook(({ d }: { d: number }) => useFuelPrices(d), {
      initialProps: { d: 30 },
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ d: 7 });
    await waitFor(() => expect(seenDays).toEqual(expect.arrayContaining(['30', '7'])));
  });

  it('surfaces 503 as error', async () => {
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', () =>
        HttpResponse.json({ error: 'csv missing' }, { status: 503 }),
      ),
    );
    const { result } = renderHook(() => useFuelPrices(30));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).not.toBeNull();
  });
});
