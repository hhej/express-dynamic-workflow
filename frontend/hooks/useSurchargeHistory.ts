'use client';
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { SURCHARGE_HISTORY_LIMIT } from '@/lib/constants';
import type { ConversationSummary } from '@/types/api.types';
import type { SurchargeResult } from '@/types/agent.types';

export interface SurchargeHistoryPoint {
  thread_id: string;
  /** Truncated first_message_preview for chart x-axis label. */
  label: string;
  last_updated: string;
  total: number;
  surcharge_pct: number;
  capped: boolean;
}

/**
 * D-15.2: Walk the most recent SURCHARGE_HISTORY_LIMIT threads, fetch each in
 * parallel via Promise.all (Pitfall 8 — avoid sequential N+1 latency), drop
 * threads with surcharge_result===null and threads whose individual fetch
 * fails. The hook only sets `error` if the *outer* Promise.all itself rejects
 * (which it never does because per-thread errors are caught).
 */
export function useSurchargeHistory(items: ConversationSummary[], loading: boolean) {
  const [data, setData] = useState<SurchargeHistoryPoint[]>([]);
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (loading) return;
    if (items.length === 0) {
      setData([]);
      setLoadingHistory(false);
      return;
    }

    let cancelled = false;
    setLoadingHistory(true);
    setError(null);

    const slice = items.slice(0, SURCHARGE_HISTORY_LIMIT);
    Promise.all(
      slice.map((item) =>
        api
          .getConversation(item.thread_id)
          .then((detail) => ({ item, detail }))
          .catch(() => null),
      ),
    )
      .then((results) => {
        if (cancelled) return;
        const points: SurchargeHistoryPoint[] = [];
        for (const r of results) {
          if (!r) continue;
          const sr: SurchargeResult | null = r.detail.surcharge_result;
          if (!sr) continue;
          points.push({
            thread_id: r.item.thread_id,
            label: (r.item.first_message_preview || r.item.thread_id).slice(0, 30),
            last_updated: r.item.last_updated,
            total: sr.total,
            surcharge_pct: sr.surcharge_pct,
            capped: sr.capped,
          });
        }
        // Oldest → newest for natural reading order in the chart.
        points.sort(
          (a, b) => Date.parse(a.last_updated) - Date.parse(b.last_updated),
        );
        setData(points);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [items, loading]);

  return { data, loading: loadingHistory, error };
}
