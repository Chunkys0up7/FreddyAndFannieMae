"use client";

import { useCopilotReadable } from "@copilotkit/react-core";
import type { Bulletin, ReviewStatusValue, Section } from "../lib/types";

export function useBulletinState({
  selectedBulletin,
  currentSection,
  reviewStatusMap,
}: {
  selectedBulletin: Bulletin | null;
  currentSection: Section | null;
  reviewStatusMap: Record<string, ReviewStatusValue>;
}) {
  useCopilotReadable({
    description: "The bulletin currently selected by the reviewer (id, agency, title, url).",
    value: selectedBulletin,
  });

  useCopilotReadable({
    description:
      "The full text and metadata of the section the reviewer is currently viewing. " +
      "Use this when answering questions about 'this section'.",
    value: currentSection,
  });

  useCopilotReadable({
    description:
      "Map of section_number → review status (new | reviewing | reviewed | flagged). " +
      "Use this to know whether a section has already been flagged before suggesting one.",
    value: reviewStatusMap,
  });
}
