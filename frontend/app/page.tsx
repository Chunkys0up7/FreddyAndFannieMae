"use client";

import { useCallback, useEffect, useState } from "react";
import { CopilotSidebar } from "@copilotkit/react-ui";

import BulletinFeed from "../components/BulletinFeed";
import SectionViewer from "../components/SectionViewer";
import { listBulletins, flagSection, getStats } from "../lib/api";
import type { Bulletin, ReviewStatusValue, Section } from "../lib/types";
import { useBulletinState } from "../hooks/useBulletinState";
import { useGuidelineActions } from "../hooks/useGuidelineActions";
import { useSuggestions } from "../hooks/useSuggestions";

export default function Home() {
  const [bulletins, setBulletins] = useState<Bulletin[]>([]);
  const [selectedBulletin, setSelectedBulletin] = useState<Bulletin | null>(null);
  const [currentSection, setCurrentSection] = useState<Section | null>(null);
  const [reviewStatusMap, setReviewStatusMap] = useState<
    Record<string, ReviewStatusValue>
  >({});
  const [stats, setStats] = useState<Awaited<ReturnType<typeof getStats>> | null>(null);

  useEffect(() => {
    listBulletins(undefined, 365)
      .then((data) => {
        setBulletins(data);
        const map: Record<string, ReviewStatusValue> = {};
        for (const b of data) map[b.id] = b.status;
        setReviewStatusMap((prev) => ({ ...map, ...prev }));
      })
      .catch(() => setBulletins([]));
    getStats().then(setStats).catch(() => setStats(null));
  }, []);

  const handleStatusChange = useCallback(
    (sectionNumber: string, status: "flagged" | "reviewed") => {
      setReviewStatusMap((prev) => ({ ...prev, [sectionNumber]: status }));
    },
    [],
  );

  useBulletinState({ selectedBulletin, currentSection, reviewStatusMap });
  useGuidelineActions({ onStatusChange: handleStatusChange });
  useSuggestions({ selectedBulletin, currentSection, reviewStatusMap });

  const handleFlag = useCallback(
    async (sectionNumber: string, agency: string) => {
      await flagSection({
        section_number: sectionNumber,
        agency,
        reason: "Flagged from dashboard",
        severity: "medium",
      });
      handleStatusChange(sectionNumber, "flagged");
    },
    [handleStatusChange],
  );

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b bg-slate-900 px-6 py-3 text-white">
        <div>
          <h1 className="text-lg font-semibold">GSE Guideline Copilot</h1>
          <p className="text-xs text-slate-300">
            Fannie Mae × Freddie Mac • interactive review
          </p>
        </div>
        {stats && (
          <div className="flex gap-4 text-xs">
            <Stat label="Fannie chunks" value={stats.fannie_chunks} />
            <Stat label="Freddie chunks" value={stats.freddie_chunks} />
            <Stat label="Bulletins" value={stats.bulletins} />
            <Stat label="Flagged" value={stats.review_flags} />
          </div>
        )}
      </header>

      <main className="grid flex-1 grid-cols-12 overflow-hidden">
        <aside className="col-span-3 border-r">
          <BulletinFeed
            bulletins={bulletins}
            selectedId={selectedBulletin?.id ?? null}
            onSelect={(b) => {
              setSelectedBulletin(b);
              setCurrentSection(null);
            }}
          />
        </aside>
        <section className="col-span-9 overflow-hidden">
          <SectionViewer
            bulletin={selectedBulletin}
            selectedSection={currentSection}
            onSelectSection={setCurrentSection}
            onFlag={handleFlag}
          />
        </section>
      </main>

      <CopilotSidebar
        defaultOpen={true}
        labels={{
          title: "GSE Copilot",
          initial:
            "Hi! I can answer guideline questions, compare Fannie and Freddie, " +
            "summarize bulletin impacts, and flag sections for QI review.",
        }}
        instructions="You are the GSE Guideline Copilot. Always cite section numbers."
      />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-right">
      <div className="font-mono text-base font-semibold">{value.toLocaleString()}</div>
      <div className="text-[10px] uppercase text-slate-400">{label}</div>
    </div>
  );
}
