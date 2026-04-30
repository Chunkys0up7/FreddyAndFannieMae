"use client";

import { useEffect, useState } from "react";
import type { Bulletin, Section } from "../lib/types";
import { searchSections } from "../lib/api";
import CitationCard from "./CitationCard";

export default function SectionViewer({
  bulletin,
  selectedSection,
  onSelectSection,
  onFlag,
}: {
  bulletin: Bulletin | null;
  selectedSection: Section | null;
  onSelectSection: (s: Section | null) => void;
  onFlag: (sectionNumber: string, agency: string) => void;
}) {
  const [related, setRelated] = useState<Section[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!bulletin) {
      setRelated([]);
      return;
    }
    setLoading(true);
    searchSections(bulletin.title || bulletin.id, bulletin.agency, 5)
      .then(setRelated)
      .catch(() => setRelated([]))
      .finally(() => setLoading(false));
  }, [bulletin]);

  if (!bulletin) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-slate-400">
        Select a bulletin to view affected sections.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <header className="border-b bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-0.5 text-xs font-semibold uppercase text-white ${
              bulletin.agency === "fannie" ? "bg-fannie" : "bg-freddie"
            }`}
          >
            {bulletin.agency === "fannie" ? "Fannie Mae" : "Freddie Mac"}
          </span>
          <span className="font-mono text-sm font-bold">{bulletin.id}</span>
        </div>
        <h1 className="mt-1 text-base font-semibold">{bulletin.title || "(untitled)"}</h1>
        <a
          href={bulletin.url}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-700 underline"
        >
          Open source →
        </a>
      </header>

      <div className="px-4 py-3">
        <div className="mb-2 text-xs font-semibold uppercase text-slate-500">
          Affected sections {loading && "(loading…)"}
        </div>
        <div className="space-y-2">
          {related.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelectSection(s)}
              className="w-full text-left"
            >
              <CitationCard
                citation={{
                  agency: s.metadata.agency,
                  section_number: s.metadata.section_number,
                  section_title: s.metadata.section_title,
                  source_url: s.metadata.source_url,
                }}
              />
            </button>
          ))}
        </div>

        {selectedSection && (
          <div className="mt-4 rounded-lg border bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <div className="font-mono text-sm font-bold">
                {selectedSection.metadata.section_number} — {selectedSection.metadata.section_title}
              </div>
              <button
                onClick={() =>
                  onFlag(
                    selectedSection.metadata.section_number,
                    selectedSection.metadata.agency,
                  )
                }
                className="rounded bg-rose-600 px-3 py-1 text-xs font-medium text-white hover:bg-rose-700"
              >
                Flag for QI Review
              </button>
            </div>
            <div className="whitespace-pre-wrap text-sm text-slate-700">
              {selectedSection.text}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
