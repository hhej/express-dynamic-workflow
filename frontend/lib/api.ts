import { API_BASE_URL } from '@/lib/constants';
import type {
  ChatRequest,
  ConversationDetail,
  ConversationSummary,
  FuelPricePoint,
} from '@/types/api.types';

/**
 * Thrown by the JSON GET helpers when the backend returns a non-2xx status.
 * Carries the HTTP status code so callers can branch on retryability.
 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function jsonGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} failed: ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  listConversations: (limit = 50) =>
    jsonGet<ConversationSummary[]>(`/api/conversations?limit=${limit}`),

  getConversation: (threadId: string) =>
    jsonGet<ConversationDetail>(`/api/conversations/${threadId}`),

  fuelPrices: (days = 30) =>
    jsonGet<FuelPricePoint[]>(`/api/fuel-prices?days=${days}`),

  /**
   * POST /api/chat — returns the raw Response so the caller can pipe
   * `response.body` into parseSseStream. Do NOT call .json() here.
   */
  postChat: (body: ChatRequest, signal?: AbortSignal) =>
    fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    }),
};
