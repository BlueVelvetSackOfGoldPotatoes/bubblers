from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from app.models import BubbleVersion, Comment


_STOPWORDS = {
    "a","an","the","and","or","but","if","then","else","when","while","of","to","in","on","for","with","as","at",
    "by","from","is","are","was","were","be","been","being","it","this","that","these","those","i","you","he","she",
    "they","we","me","him","her","them","us","my","your","our","their","mine","yours","ours","theirs","not","no",
    "do","does","did","doing","done","can","could","should","would","will","just","so","very","really","about",
    "what","which","who","whom","why","how","also","too","more","most","some","any","all","many","much","few",
}


_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class LabelerConfig:
    mode: str = "mocked"
    max_representatives: int = 5


class MockLabeler:
    """
    Deterministic labeler for demo use.

    Args:
        config: LabelerConfig controlling representative count.

    Returns:
        (label, essence, confidence, representative_comment_ids)
    """

    def __init__(self, config: LabelerConfig) -> None:
        self._config = config

    def label(self, bubble_version: BubbleVersion, comments_by_id: Dict[str, Comment]) -> Tuple[str, str, float, List[str]]:
        comments = [comments_by_id[cid] for cid in bubble_version.comment_ids if cid in comments_by_id]
        rep_ids = self._choose_representatives([c.id for c in comments])
        rep_texts = [comments_by_id[cid].text for cid in rep_ids if cid in comments_by_id]
        keywords = self._top_keywords(rep_texts if rep_texts else [c.text for c in comments], k=3)

        if keywords:
            label = " / ".join(w.title() for w in keywords)
        else:
            label = "Miscellaneous"

        if len(keywords) >= 2:
            essence = f"People are discussing {keywords[0]} and {keywords[1]}, with related points and reactions."
        elif len(keywords) == 1:
            essence = f"People are discussing {keywords[0]}, sharing viewpoints and related details."
        else:
            essence = "People are reacting and sharing viewpoints, with multiple loosely related points."

        n = len(bubble_version.comment_ids)
        confidence = min(1.0, math.log(1 + n) / math.log(1 + 10))

        return label, essence, confidence, rep_ids

    def _choose_representatives(self, comment_ids: Sequence[str]) -> List[str]:
        if not comment_ids:
            return []
        if len(comment_ids) <= self._config.max_representatives:
            return list(comment_ids)
        idxs = []
        steps = self._config.max_representatives
        for i in range(steps):
            t = i / (steps - 1)
            idx = int(round(t * (len(comment_ids) - 1)))
            idxs.append(idx)
        uniq = []
        seen = set()
        for i in idxs:
            cid = comment_ids[i]
            if cid not in seen:
                seen.add(cid)
                uniq.append(cid)
        return uniq

    def _top_keywords(self, texts: Sequence[str], k: int) -> List[str]:
        counts: Dict[str, int] = {}
        for text in texts:
            for tok in _TOKEN_RE.findall(text.lower()):
                if tok in _STOPWORDS:
                    continue
                if len(tok) <= 2:
                    continue
                counts[tok] = counts.get(tok, 0) + 1
        if not counts:
            return []
        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return [w for w, _ in ranked[:k]]
