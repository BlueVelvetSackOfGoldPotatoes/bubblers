from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from app.models import BubbleVersion, Comment

load_dotenv()


@dataclass(frozen=True)
class LabelerConfig:
    mode: str = "live"
    max_representatives: int = 5


class GPTLabeler:
    """
    GPT-based labeler for generating bubble labels and essences.

    Args:
        config: LabelerConfig controlling representative count.

    Returns:
        (label, essence, confidence, representative_comment_ids)
    """

    def __init__(self, config: LabelerConfig) -> None:
        self._config = config
        api_key = os.getenv("GPT_KEY")
        if not api_key:
            raise ValueError("GPT_KEY not found in environment variables")
        self._client = OpenAI(api_key=api_key)

    def label(self, bubble_version: BubbleVersion, comments_by_id: Dict[str, Comment]) -> Tuple[str, str, float, List[str]]:
        comments = [comments_by_id[cid] for cid in bubble_version.comment_ids if cid in comments_by_id]
        rep_ids = self._choose_representatives([c.id for c in comments])
        rep_texts = [comments_by_id[cid].text for cid in rep_ids if cid in comments_by_id]
        
        if not rep_texts:
            return "Miscellaneous", "No comments available.", 0.0, []

        total_text_length = sum(len(t) for t in rep_texts)
        if total_text_length > 4000:
            rep_texts = rep_texts[:3]
        
        comments_text = "\n\n".join(f"Comment {i+1}: {text}" for i, text in enumerate(rep_texts))
        
        prompt = f"""Analyze the following comments and provide:
1. A concise label (2-4 words, use " / " to separate multiple topics)
2. A brief essence (1-2 sentences describing what people are discussing)

Comments:
{comments_text}

Respond in this exact format:
LABEL: [your label here]
ESSENCE: [your essence here]"""

        label = "Miscellaneous"
        essence = "People are discussing various topics."
        
        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes comment clusters and generates concise labels and summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=200,
            )
            
            result = response.choices[0].message.content or ""
            
            for line in result.split("\n"):
                line = line.strip()
                if line.upper().startswith("LABEL:"):
                    label = line[6:].strip()
                elif line.upper().startswith("ESSENCE:"):
                    essence = line[8:].strip()
            
            if not label:
                label = "Miscellaneous"
            if not essence:
                essence = "People are discussing various topics."
                
        except (APIError, APIConnectionError, APITimeoutError) as e:
            label = "Miscellaneous"
            essence = f"Error generating label: {type(e).__name__}"
        except Exception as e:
            label = "Miscellaneous"
            essence = "People are discussing various topics."

        rep_ids_set = set(rep_ids)
        comment_ids_set = set(bubble_version.comment_ids)
        valid_rep_ids = [rid for rid in rep_ids if rid in comment_ids_set]
        
        if not valid_rep_ids and rep_ids:
            valid_rep_ids = list(bubble_version.comment_ids[:min(len(bubble_version.comment_ids), self._config.max_representatives)])
        
        n = len(bubble_version.comment_ids)
        confidence = min(1.0, math.log(1 + n) / math.log(1 + 10))

        return label, essence, confidence, valid_rep_ids

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
