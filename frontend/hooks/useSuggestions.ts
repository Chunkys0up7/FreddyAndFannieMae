"use client";

import { useCopilotChatSuggestions } from "@copilotkit/react-ui";
import type { Bulletin, ReviewStatusValue, Section } from "../lib/types";

export function useSuggestions({
  selectedBulletin,
  currentSection,
  reviewStatusMap,
}: {
  selectedBulletin: Bulletin | null;
  currentSection: Section | null;
  reviewStatusMap: Record<string, ReviewStatusValue>;
}) {
  let instructions = "Suggest 3 short next-step questions a QI reviewer would ask.";

  if (selectedBulletin) {
    instructions += ` A bulletin (${selectedBulletin.id}, ${selectedBulletin.agency}) is selected. Suggest:
      1) "What sections does ${selectedBulletin.id} change?"
      2) "Compare with the other agency's policy on this topic."
      3) "Generate a gap note for the most affected section."`;
  } else if (currentSection) {
    const flagged = reviewStatusMap[currentSection.metadata.section_number] === "flagged";
    instructions += ` The reviewer is viewing ${currentSection.metadata.section_number} — ${currentSection.metadata.section_title}. Suggest:
      1) "Compare with the other agency on ${currentSection.metadata.section_title}."
      ${flagged
        ? '2) "Generate a gap note for this section."\n3) "Mark this section reviewed."'
        : '2) "Flag this section for QI review."\n3) "What recently changed in this section?"'}`;
  } else {
    instructions += ` No bulletin or section is selected. Suggest:
      1) "Show me the latest Fannie Mae bulletins."
      2) "What are the gift fund requirements?"
      3) "Compare Fannie and Freddie on credit score minimums."`;
  }

  useCopilotChatSuggestions(
    {
      instructions,
      minSuggestions: 1,
      maxSuggestions: 3,
    },
    [selectedBulletin?.id, currentSection?.id, JSON.stringify(reviewStatusMap)],
  );
}
