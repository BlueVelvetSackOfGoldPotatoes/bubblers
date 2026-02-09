from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from app.models import BubbleVersion, Comment
from app.pipeline.providers import Labeler

_STOP_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "all", "both", "each", "few", "more", "most",
    "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "just", "because", "but",
    "and", "or", "if", "while", "it", "its", "i", "you", "he", "she",
    "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "their", "this", "that", "these", "those", "what", "which",
    "who", "whom", "am", "about", "up", "also", "really", "like",
    "get", "got", "much", "one", "dont", "even", "still", "think",
    "know", "going", "went", "im", "ive", "thats", "thing", "things",
    "people", "way", "make", "many", "well", "something", "anything",
})


class LocalLabeler(Labeler):
    """Extractive labeler using keyword frequency."""

    def __init__(self, max_representatives: int = 5) -> None:
        self._max_representatives = max_representatives

    def label(
        self, bubble_version: BubbleVersion, comments_by_id: Dict[str, Comment]
    ) -> Tuple[str, str, float, List[str]]:
        comments = [comments_by_id[cid] for cid in bubble_version.comment_ids if cid in comments_by_id]
        rep_ids = self._choose_representatives([c.id for c in comments])
        rep_texts = [comments_by_id[cid].text for cid in rep_ids if cid in comments_by_id]

        if not rep_texts:
            return "Miscellaneous", "No comments available.", 0.0, []

        # Extract keywords from all comment texts
        all_text = " ".join(c.text for c in comments)
        words = re.findall(r"[a-zA-Z]+", all_text.lower())
        filtered = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
        counter = Counter(filtered)
        top_words = [w for w, _ in counter.most_common(4)]

        label_text = " / ".join(top_words[:3]).title() if top_words else "Miscellaneous"

        # Essence: first sentence of most representative comment
        first_rep = rep_texts[0]
        sentences = re.split(r"[.!?]+", first_rep)
        essence = (sentences[0].strip()[:150] + "...") if sentences and sentences[0].strip() else "Various discussion topics."

        n = len(bubble_version.comment_ids)
        confidence = min(1.0, math.log(1 + n) / math.log(1 + 10))

        valid_rep_ids = [rid for rid in rep_ids if rid in set(bubble_version.comment_ids)]
        return label_text, essence, confidence, valid_rep_ids

    def _choose_representatives(self, comment_ids: Sequence[str]) -> List[str]:
        if not comment_ids:
            return []
        if len(comment_ids) <= self._max_representatives:
            return list(comment_ids)
        idxs = []
        steps = self._max_representatives
        for i in range(steps):
            t = i / (steps - 1)
            idx = int(round(t * (len(comment_ids) - 1)))
            idxs.append(idx)
        uniq: List[str] = []
        seen: set[str] = set()
        for i in idxs:
            cid = comment_ids[i]
            if cid not in seen:
                seen.add(cid)
                uniq.append(cid)
        return uniq
