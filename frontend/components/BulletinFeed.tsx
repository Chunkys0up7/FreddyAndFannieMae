"use client";

import type { Bulletin } from "../lib/types";
import ReviewStatus from "./ReviewStatus";

export default function BulletinFeed({
  bulletins,
  selectedId,
  onSelect,
}: {
  bulletins: Bulletin[];
  selectedId: string | null;
  onSelect: (b: Bulletin) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <h2 className="border-b bg-slate-50 px-4 py-3 text-sm font-semibold uppercase text-slate-700">
        Recent Bulletins
      </h2>
      <ul className="flex-1 divide-y overflow-auto">
        {bulletins.length === 0 && (
          <li className="p-4 text-sm text-slate-400">
            No bulletins yet — run <code className="rounded bg-slate-100 px-1">./scripts/seed.sh</code>.
          </li>
        )}
        {bulletins.map((b) => {
          const isSelected = b.id === selectedId;
          return (
            <li
              key={b.id}
              onClick={() => onSelect(b)}
              className={`cursor-pointer p-3 hover:bg-slate-50 ${
                isSelected ? "bg-blue-50" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-slate-700">
                  {b.id}
                </span>
                <ReviewStatus status={b.status} />
              </div>
              <div className="mt-1 text-sm font-medium text-slate-800">
                {b.title || "(no title)"}
              </div>
              <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
                <span className="uppercase">{b.agency}</span>
                <span>•</span>
                <span>{new Date(b.discovered_at).toLocaleDateString()}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
