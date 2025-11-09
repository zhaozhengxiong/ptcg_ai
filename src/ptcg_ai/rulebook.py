"""Rule knowledge base helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class RuleEntry:
    """Single rule snippet fetched from the knowledge base."""

    section: str
    text: str


@dataclass
class RuleKnowledgeBase:
    """In-memory representation of the rule knowledge base.

    The class can ingest both structured JSON exports and plain text files. For
    the sake of the prototype we extract numbered sections from the official
    rulebook PDF that has been pre-processed into text elsewhere.
    """

    rules: Dict[str, RuleEntry] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # ingestion helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_text(cls, text: str) -> "RuleKnowledgeBase":
        pattern = re.compile(r"^(\d+(?:\.\d+)*)\s+(.*)$", re.MULTILINE)
        rules: Dict[str, RuleEntry] = {}
        for match in pattern.finditer(text):
            section, body = match.groups()
            rules[section] = RuleEntry(section=section, text=body.strip())
        return cls(rules=rules)

    @classmethod
    def from_json(cls, path: Path) -> "RuleKnowledgeBase":
        data = json.loads(path.read_text(encoding="utf-8"))
        rules = {
            item["section"]: RuleEntry(section=item["section"], text=item["text"])
            for item in data
        }
        return cls(rules=rules)

    # ------------------------------------------------------------------
    # query helpers
    # ------------------------------------------------------------------
    def find(self, query: str, limit: int = 5) -> List[RuleEntry]:
        """Perform a naive substring search."""

        query_lower = query.lower()
        matches: List[RuleEntry] = []
        for entry in self.rules.values():
            if query_lower in entry.text.lower():
                matches.append(entry)
            if len(matches) >= limit:
                break
        return matches

    def get(self, section: str) -> Optional[RuleEntry]:
        return self.rules.get(section)

    def __iter__(self) -> Iterable[RuleEntry]:
        yield from self.rules.values()


__all__ = ["RuleKnowledgeBase", "RuleEntry"]
