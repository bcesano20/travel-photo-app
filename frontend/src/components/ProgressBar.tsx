interface ProgressBarProps {
  value: number; /** Items finished so far. */
  total: number; /** Total items expected. */
  label?: string;
  className?: string;
}

export const ProgressBar = ({ value, total, label, className }: ProgressBarProps) => {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0;

  return (
    <div className={className}>
      <div className="mb-1 flex items-center justify-between text-xs text-white">
        <span>{label}</span>
        <span>
          {value} / {total} ({percentage}%)
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={value}
        aria-label={label}
        className="h-2.5 w-full overflow-hidden rounded-full bg-neutral-700"
      >
        <div
          className="h-full rounded-full bg-emerald-500 transition-[width] duration-300 ease-out"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
