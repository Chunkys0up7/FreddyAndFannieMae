export type Agency = "fannie" | "freddie";

export type Bulletin = {
  id: string;
  agency: Agency;
  url: string;
  title: string | null;
  published: string | null;
  discovered_at: string;
  status: ReviewStatusValue;
};

export type ReviewStatusValue = "new" | "reviewing" | "reviewed" | "flagged";

export type Section = {
  id: string;
  text: string;
  metadata: {
    section_number: string;
    section_title: string;
    agency: Agency;
    doc_type: "guide" | "bulletin";
    source_url?: string;
    bulletin_id?: string;
  };
  distance: number;
};

export type Citation = {
  agency: Agency;
  section_number: string;
  section_title: string;
  source_url?: string | null;
};

export type ComparisonRow = {
  fannie: Section[];
  freddie: Section[];
};

export type DiffPayload = {
  added: string[];
  removed: string[];
  changed: { old: string[]; new: string[] }[];
  unified: string;
};

export type ReviewFlag = {
  id: number;
  section_number: string;
  agency: Agency;
  reason: string;
  severity: string;
  reviewer?: string | null;
  flagged_at: string;
  status: ReviewStatusValue;
};
