'use client';
import { useEffect, useState } from 'react';
import type { ApprovalPayload } from '@/types/agent.types';

interface Props {
  payload: ApprovalPayload;
  onApprove: () => void | Promise<void>;
  onDeny: () => void | Promise<void>;
  /** Plan 06-02 D-10 — when set, renders an inline red error line below the buttons. Buttons stay clickable per D-11. */
  errorMessage?: string | null;
}

/**
 * Plan 05-05 D-06 / D-07 inline approval prompt. Yellow-50/yellow-300 palette
 * (matches CapCallout) signals "review required" without inventing a new
 * color. Approve and Deny buttons use NEUTRAL outline (not accent blue) —
 * D-07 requires deliberate user choice. Body copy uses Bangkok Metro phrasing
 * (UI-SPEC §Copywriting — never "Central Region").
 *
 * Plan 06-02 D-10: optional `errorMessage` renders an inline red line below
 * the buttons when an approve/deny POST fails. Buttons stay clickable so the
 * user can retry without dismissing (D-11).
 */
export function ApprovalCard({ payload, onApprove, onDeny, errorMessage }: Props) {
  const [waiting, setWaiting] = useState(false);
  const total = formatTHB(payload.surcharge_result.total);
  const threshold = formatTHB(payload.threshold);

  // Plan 06-02 D-11: when the parent surfaces an errorMessage, the prior
  // approve/deny POST failed — reset the waiting flag so both buttons stay
  // clickable for retry without dismissing the card.
  useEffect(() => {
    if (errorMessage) {
      setWaiting(false);
    }
  }, [errorMessage]);

  async function handle(action: () => void | Promise<void>) {
    setWaiting(true);
    try {
      await action();
    } catch {
      // Reset so user can retry; useChatStream surfaces ERROR state.
      setWaiting(false);
    }
  }

  // Buttons disabled while in flight, but a parent-supplied errorMessage
  // forces them re-enabled (D-11 — clickable on POST error).
  const buttonsDisabled = waiting && !errorMessage;

  return (
    <div className="rounded border border-yellow-300 bg-yellow-50 p-4 text-yellow-900">
      <h3 className="text-base font-semibold leading-tight">
        Approval required
      </h3>
      <p className="mt-2 text-sm leading-normal">
        This Bangkok Metro shipment surcharge total of {total} THB exceeds the
        review threshold of {threshold} THB. Review the breakdown below before
        approving.
      </p>
      <div className="mt-3">
        <h4 className="text-sm font-semibold">Recommended surcharge</h4>
        <table className="mt-1 w-full border-collapse text-sm">
          <tbody>
            <tr>
              <td className="border px-2 py-1">Surcharge %</td>
              <td className="border px-2 py-1">
                {(payload.surcharge_result.surcharge_pct * 100).toFixed(2)}%
              </td>
            </tr>
            <tr>
              <td className="border px-2 py-1">Surcharge amount</td>
              <td className="border px-2 py-1">
                {formatTHB(payload.surcharge_result.surcharge_amount)} THB
              </td>
            </tr>
            <tr>
              <td className="border px-2 py-1">Total</td>
              <td className="border px-2 py-1">{total} THB</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex gap-1">
        <button
          type="button"
          aria-label="Approve recommended surcharge"
          disabled={buttonsDisabled}
          onClick={() => handle(onApprove)}
          className="rounded border border-gray-300 bg-white px-4 py-2 text-base font-semibold text-gray-900 hover:bg-gray-100 disabled:opacity-60"
        >
          Approve
        </button>
        <button
          type="button"
          aria-label="Deny recommended surcharge"
          disabled={buttonsDisabled}
          onClick={() => handle(onDeny)}
          className="rounded border border-gray-300 bg-white px-4 py-2 text-base font-semibold text-gray-900 hover:bg-gray-100 disabled:opacity-60"
        >
          Deny
        </button>
      </div>
      {errorMessage && (
        <p
          role="alert"
          className="mt-2 text-sm text-red-700"
        >
          {errorMessage}
        </p>
      )}
      {waiting && (
        <p
          role="status"
          aria-live="polite"
          className="mt-2 text-xs italic text-yellow-900"
        >
          Sending your decision…
        </p>
      )}
    </div>
  );
}

function formatTHB(n: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(n);
}
