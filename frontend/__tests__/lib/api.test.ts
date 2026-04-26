import { describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { api, ApiError } from '@/lib/api';
import { server } from '../mocks/server';

describe('api client', () => {
  it('listConversations returns the MSW-mocked thread list', async () => {
    const items = await api.listConversations();
    expect(items.length).toBeGreaterThan(0);
    expect(items[0]).toHaveProperty('thread_id');
    expect(items[0]).toHaveProperty('first_message_preview');
  });

  it('getConversation returns detail with surcharge_result populated', async () => {
    const detail = await api.getConversation('thread-1');
    expect(detail.thread_id).toBe('thread-1');
    expect(detail.surcharge_result?.total).toBe(152.5);
  });

  it('fuelPrices(7) sends ?days=7 in the URL', async () => {
    let receivedUrl = '';
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', ({ request }) => {
        receivedUrl = request.url;
        return HttpResponse.json([]);
      }),
    );
    await api.fuelPrices(7);
    expect(receivedUrl).toContain('days=7');
  });

  it('postChat returns a Response object suitable for streaming', async () => {
    const res = await api.postChat({ message: 'hi' });
    expect(res).toBeInstanceOf(Response);
    expect(res.body).toBeTruthy();
  });

  it('throws ApiError when GET endpoint returns 503', async () => {
    server.use(
      http.get('http://localhost:8000/api/fuel-prices', () =>
        HttpResponse.json({ error: 'csv missing' }, { status: 503 }),
      ),
    );
    await expect(api.fuelPrices(30)).rejects.toBeInstanceOf(ApiError);
    await expect(api.fuelPrices(30)).rejects.toMatchObject({ status: 503 });
  });
});
