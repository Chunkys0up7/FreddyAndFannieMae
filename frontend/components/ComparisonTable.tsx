import type { Section } from "../lib/types";

export default function ComparisonTable({
  fannie,
  freddie,
  topic,
}: {
  fannie: Section[];
  freddie: Section[];
  topic?: string;
}) {
  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      {topic && (
        <h3 className="mb-3 text-sm font-semibold text-slate-700">
          Comparison: {topic}
        </h3>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Column title="Fannie Mae" sections={fannie} accent="fannie" />
        <Column title="Freddie Mac" sections={freddie} accent="freddie" />
      </div>
    </div>
  );
}

function Column({
  title,
  sections,
  accent,
}: {
  title: string;
  sections: Section[];
  accent: "fannie" | "freddie";
}) {
  const headerClass = accent === "fannie" ? "bg-fannie text-white" : "bg-freddie text-white";
  return (
    <div className="rounded border">
      <div className={`px-3 py-1 text-xs font-semibold uppercase ${headerClass}`}>
        {title}
      </div>
      <ul className="divide-y">
        {sections.map((s) => (
          <li key={s.id} className="p-3 text-sm">
            <div className="font-mono text-xs text-slate-500">
              {s.metadata.section_number}
            </div>
            <div className="font-medium">{s.metadata.section_title}</div>
            <div className="mt-1 line-clamp-3 text-xs text-slate-600">
              {s.text.slice(0, 240)}…
            </div>
          </li>
        ))}
        {sections.length === 0 && (
          <li className="p-3 text-xs text-slate-400">No matches.</li>
        )}
      </ul>
    </div>
  );
}
