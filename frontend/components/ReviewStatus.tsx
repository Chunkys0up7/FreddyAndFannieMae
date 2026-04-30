import type { ReviewStatusValue } from "../lib/types";

const COLORS: Record<ReviewStatusValue, string> = {
  new: "bg-slate-200 text-slate-700",
  reviewing: "bg-amber-100 text-amber-800",
  reviewed: "bg-emerald-100 text-emerald-800",
  flagged: "bg-rose-100 text-rose-800",
};

export default function ReviewStatus({ status }: { status: ReviewStatusValue }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium uppercase ${COLORS[status]}`}
    >
      {status}
    </span>
  );
}
