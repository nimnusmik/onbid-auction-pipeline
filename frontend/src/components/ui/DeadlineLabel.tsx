import { dLabel, daysLeft } from "@/utils/format";

export default function DeadlineLabel({
  dt,
  pvct,
}: {
  dt: string;
  pvct: boolean;
}) {
  const dl = daysLeft(dt);
  const cls =
    dl < 0
      ? "text-text-4"
      : dl <= 3
      ? "text-urgent font-semibold"
      : "text-text-2";
  return (
    <div className={`text-xs whitespace-nowrap ${cls}`}>
      <div>{dLabel(dt)}</div>
      {pvct && (
        <span className="inline-block mt-0.5 text-[10px] bg-mid-bg text-mid-fg rounded px-1.5 py-0.5 font-semibold">
          수의계약
        </span>
      )}
    </div>
  );
}
