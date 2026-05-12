import clsx from 'clsx';

export function LoadingSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        'animate-pulse rounded bg-white/5',
        className ?? 'h-4 w-full',
      )}
      aria-hidden
    />
  );
}
