import type { Bulletin, ReviewFlag, Section } from "./types";

const PIPELINE_URL =
  process.env.NEXT_PUBLIC_PIPELINE_API_URL ||
  process.env.PIPELINE_API_URL ||
  "http://localhost:8001";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${PIPELINE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export async function listBulletins(agency?: string, days = 90): Promise<Bulletin[]> {
  const qs = new URLSearchParams();
  if (agency) qs.set("agency", agency);
  qs.set("days", String(days));
  return jsonFetch(`/bulletins?${qs.toString()}`);
}

export async function searchSections(
  q: string,
  agency?: string,
  topK = 5,
): Promise<Section[]> {
  const qs = new URLSearchParams({ q, top_k: String(topK) });
  if (agency) qs.set("agency", agency);
  return jsonFetch(`/sections/search?${qs.toString()}`);
}

export async function listReviews(agency?: string): Promise<ReviewFlag[]> {
  const qs = new URLSearchParams();
  if (agency) qs.set("agency", agency);
  return jsonFetch(`/reviews?${qs.toString()}`);
}

export async function flagSection(payload: {
  section_number: string;
  agency: string;
  reason: string;
  severity?: string;
  reviewer?: string;
}) {
  return jsonFetch(`/reviews/flag`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function markReviewed(payload: {
  section_number: string;
  notes?: string;
  reviewer?: string;
}) {
  return jsonFetch(`/reviews/mark-reviewed`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createGapNote(payload: {
  section_number: string;
  agency: string;
  current_sop: string;
  change: string;
  recommendation: string;
}) {
  return jsonFetch(`/reviews/gap-note`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getStats() {
  return jsonFetch<{
    fannie_chunks: number;
    freddie_chunks: number;
    bulletin_chunks: number;
    bulletins: number;
    review_flags: number;
  }>(`/stats`);
}
