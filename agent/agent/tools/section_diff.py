"""Compute structured diff between old and new section text."""
from __future__ import annotations

import difflib


def section_diff(old_text: str, new_text: str) -> dict:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    added: list[str] = []
    removed: list[str] = []
    changed: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added.extend(new_lines[j1:j2])
        elif tag == "delete":
            removed.extend(old_lines[i1:i2])
        elif tag == "replace":
            changed.append(
                {"old": old_lines[i1:i2], "new": new_lines[j1:j2]}
            )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unified": "\n".join(
            difflib.unified_diff(old_lines, new_lines, lineterm="", n=2)
        ),
    }
