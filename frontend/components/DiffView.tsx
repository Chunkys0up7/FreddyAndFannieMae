import type { DiffPayload } from "../lib/types";

export default function DiffView({
  diff,
  oldTitle = "Before",
  newTitle = "After",
}: {
  diff: DiffPayload;
  oldTitle?: string;
  newTitle?: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-slate-700">Change Diff</h3>
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="mb-1 font-semibold text-red-700">{oldTitle}</div>
          <ul className="space-y-1">
            {diff.removed.map((line, i) => (
              <li key={`r-${i}`} className="rounded bg-red-50 px-2 py-1 font-mono text-red-900">
                − {line}
              </li>
            ))}
            {diff.removed.length === 0 && (
              <li className="text-slate-400">(no removals)</li>
            )}
          </ul>
        </div>
        <div>
          <div className="mb-1 font-semibold text-green-700">{newTitle}</div>
          <ul className="space-y-1">
            {diff.added.map((line, i) => (
              <li
                key={`a-${i}`}
                className="rounded bg-green-50 px-2 py-1 font-mono text-green-900"
              >
                + {line}
              </li>
            ))}
            {diff.added.length === 0 && (
              <li className="text-slate-400">(no additions)</li>
            )}
          </ul>
        </div>
      </div>
      {diff.changed.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs font-semibold text-amber-700">Changed</div>
          <ul className="space-y-1 text-xs">
            {diff.changed.map((c, i) => (
              <li key={`c-${i}`} className="rounded border-l-4 border-amber-400 bg-amber-50 p-2">
                <div className="text-red-700 line-through">{c.old.join(" ")}</div>
                <div className="text-green-700">{c.new.join(" ")}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
