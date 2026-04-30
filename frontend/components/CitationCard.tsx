import type { Citation } from "../lib/types";

export default function CitationCard({ citation }: { citation: Citation }) {
  const isFannie = citation.agency === "fannie";
  const badgeClass = isFannie ? "bg-fannie text-white" : "bg-freddie text-white";
  const cardClass = isFannie
    ? "border-fannie/30 bg-fannie-light/50"
    : "border-freddie/30 bg-freddie-light/50";

  return (
    <div className={`rounded-lg border p-3 ${cardClass}`}>
      <div className="flex items-center gap-2">
        <span
          className={`inline-block rounded px-2 py-0.5 text-xs font-semibold uppercase ${badgeClass}`}
        >
          {isFannie ? "Fannie Mae" : "Freddie Mac"}
        </span>
        <span className="font-mono text-sm font-bold">{citation.section_number}</span>
      </div>
      <div className="mt-1 text-sm font-medium">{citation.section_title}</div>
      {citation.source_url && (
        <a
          className="mt-1 inline-block text-xs text-blue-700 underline"
          href={citation.source_url}
          target="_blank"
          rel="noreferrer"
        >
          View source →
        </a>
      )}
    </div>
  );
}
