"use client";

import { useCopilotAction } from "@copilotkit/react-core";
import { createGapNote, flagSection, markReviewed } from "../lib/api";

export function useGuidelineActions({
  onStatusChange,
}: {
  onStatusChange: (sectionNumber: string, status: "flagged" | "reviewed") => void;
}) {
  useCopilotAction({
    name: "flag_for_qi_review",
    description:
      "Flag a guideline section for QI team review. Use when the user asks to flag, " +
      "escalate, or mark a section for the QI review queue.",
    parameters: [
      { name: "sectionNumber", type: "string", description: "GSE section number, e.g. B3-4.3-04" },
      { name: "agency", type: "string", description: "Agency: fannie | freddie" },
      { name: "reason", type: "string", description: "Why this needs review" },
      { name: "severity", type: "string", description: "low | medium | high", required: false },
    ],
    handler: async ({ sectionNumber, agency, reason, severity }) => {
      await flagSection({
        section_number: sectionNumber,
        agency,
        reason,
        severity: severity || "medium",
      });
      onStatusChange(sectionNumber, "flagged");
      return `Flagged ${sectionNumber} (${severity || "medium"} severity).`;
    },
  });

  useCopilotAction({
    name: "mark_section_reviewed",
    description:
      "Mark a guideline section as reviewed. Use when the user confirms the section " +
      "has been reviewed and no further action is needed.",
    parameters: [
      { name: "sectionNumber", type: "string", description: "GSE section number" },
      { name: "notes", type: "string", description: "Optional review notes", required: false },
    ],
    handler: async ({ sectionNumber, notes }) => {
      await markReviewed({ section_number: sectionNumber, notes });
      onStatusChange(sectionNumber, "reviewed");
      return `Marked ${sectionNumber} as reviewed.`;
    },
  });

  useCopilotAction({
    name: "generate_sop_gap_note",
    description:
      "Create a structured gap note describing the difference between the current " +
      "internal SOP and an updated GSE guideline.",
    parameters: [
      { name: "sectionNumber", type: "string" },
      { name: "agency", type: "string" },
      { name: "currentSop", type: "string", description: "Current SOP text" },
      { name: "change", type: "string", description: "What changed in the guideline" },
      { name: "recommendation", type: "string", description: "Recommended SOP update" },
    ],
    handler: async ({ sectionNumber, agency, currentSop, change, recommendation }) => {
      const result = await createGapNote({
        section_number: sectionNumber,
        agency,
        current_sop: currentSop,
        change,
        recommendation,
      });
      return `Gap note #${(result as any).id} created for ${sectionNumber}.`;
    },
  });
}
