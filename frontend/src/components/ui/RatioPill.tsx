export default function RatioPill({ ratio }: { ratio: number }) {
  const cls =
    ratio < 20
      ? "bg-hot-fg text-white"
      : ratio < 50
      ? "bg-hot-bg text-hot-fg"
      : ratio < 70
      ? "bg-mid-bg text-mid-fg"
      : "bg-primary-subtle text-primary";
  return (
    <span
      className={`inline-block ${cls} rounded-full px-2.5 py-0.5 text-sm font-semibold tabular-nums`}
    >
      {ratio.toFixed(1)}%
    </span>
  );
}
