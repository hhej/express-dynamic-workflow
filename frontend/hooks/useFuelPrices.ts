'use client';
import { useEffect, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { DEFAULT_RANGE_DAYS } from '@/lib/constants';
import type { FuelPricePoint } from '@/types/api.types';

/**
 * Hook for the fuel-price chart. Re-fetches whenever `days` changes.
 * Cancels previous fetches via a `cancelled` flag (avoids race condition
 * where a slow earlier request resolves after a newer one).
 */
export function useFuelPrices(days: number = DEFAULT_RANGE_DAYS) {
  const [data, setData] = useState<FuelPricePoint[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .fuelPrices(days)
      .then((next) => {
        if (!cancelled) setData(next);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [days]);

  return { data, loading, error };
}
