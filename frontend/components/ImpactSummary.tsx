"use client";

import type { Bulletin, Section } from "../lib/types";

export default function ImpactSummary({
  bulletin,
  sections,
  onFlag,
}: {
  bulletin: Bulletin | { id: string; agency: string; title?: string | null; url?: string };
  sections: Section[];
  onFlag?: (sectionNumber: string) => void;
}) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <span className="rounded bg-amber-500 px-2 py-0.5 text-xs font-semibold uppercase text-white">
          Bulletin
        </span>
        <span className="font-mono text-sm font-bold">{bulletin.id}</span>
        <span className="text-xs uppercase text-slate-500">{bulletin.agency}</span>
      </div>
      {bulletin.title && (
        <div className="text-sm font-medium">{bulletin.title}</div>
      )}
      <div className="mt-3">
        <div className="mb-1 text-xs font-semibold uppercase text-slate-600">
          Affected sections
        </div>
        <ul className="divide-y rounded border">
          {sections.slice(0, 6).map((s) => (
            <li key={s.id} className="flex items-center justify-between p-2 text-sm">
              <div>
                <span className="font-mono text-xs text-slate-500">
                  {s.metadata.section_number}
                </span>{" "}
                <span className="font-medium">{s.metadata.section_title}</span>
              </div>
              {onFlag && (
                <button
                  onClick={() => onFlag(s.metadata.section_number)}
                  className="rounded bg-rose-600 px-2 py-1 text-xs font-medium text-white hover:bg-rose-700"
                >
                  Flag
                </button>
              )}
            </li>
          ))}
          {sections.length === 0 && (
            <li className="p-2 text-xs text-slate-400">No sections retrieved.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
