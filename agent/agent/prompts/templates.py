"""Structured response prompts."""

QA_TEMPLATE = """Answer the user's guideline question using ONLY the retrieved sections below.

Retrieved sections (each shown as `[agency] section_number — section_title`):
{retrieved}

Question: {question}

Format:
1. One-sentence direct answer.
2. Supporting detail (2-4 sentences max).
3. Citations: list each cited section as `(agency) section_number — section_title`.

If the retrieved sections do not contain the answer, say "The retrieved sections do not directly answer this — recommend reviewing [section] for the closest related guidance."
"""

COMPARE_TEMPLATE = """Compare Fannie Mae and Freddie Mac on the user's topic.

Fannie sections:
{fannie}

Freddie sections:
{freddie}

Topic: {topic}

Output JSON only, no commentary:
{{
  "fannie": {{"section": "B3-4.3-04", "title": "Personal Gifts", "requirement": "1-2 sentence summary"}},
  "freddie": {{"section": "5501.3", "title": "...", "requirement": "..."}},
  "key_difference": "1 sentence highlighting the most material divergence"
}}
"""

DIFF_TEMPLATE = """Summarize what this bulletin changed in the affected sections.

Bulletin: {bulletin_id} — {bulletin_title}
Affected section: {section_number} — {section_title}

Old content:
{old}

New content:
{new}

Computed diff:
{diff}

Output JSON only:
{{
  "summary": "1-2 sentence change summary",
  "severity": "high | medium | low",
  "affected_section": "{section_number}",
  "before": "1 sentence prior policy",
  "after": "1 sentence new policy"
}}
"""
