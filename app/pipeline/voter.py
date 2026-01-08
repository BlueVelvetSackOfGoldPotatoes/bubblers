from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Tuple

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


@dataclass(frozen=True)
class VoterConfig:
    model: str = "gpt-4o-mini"


VoteType = Literal["agree", "disagree", "pass"]


class GPTVoter:
    """
    Classifies comments as agree, disagree, or pass (neutral) relative to the post.
    
    Args:
        config: VoterConfig controlling the model.
        
    Returns:
        VoteType classification for each comment.
    """

    def __init__(self, config: VoterConfig) -> None:
        self._config = config
        api_key = os.getenv("GPT_KEY")
        if not api_key:
            raise ValueError("GPT_KEY not found in environment variables")
        self._client = OpenAI(api_key=api_key)

    def classify(self, post_title: str, post_body: str, comment_text: str) -> VoteType:
        """
        Classify a comment as agree, disagree, or pass.
        
        Args:
            post_title: Title of the post
            post_body: Body text of the post
            comment_text: Text of the comment to classify
            
        Returns:
            "agree", "disagree", or "pass"
        """
        prompt = f"""You are analyzing a comment on a Reddit-style post. Classify the comment's stance relative to the post.

Post Title: {post_title}
Post Body: {post_body[:500]}

Comment: {comment_text[:1000]}

Classify the comment as one of:
- "agree" if the comment supports, agrees with, or positively responds to the post
- "disagree" if the comment opposes, disagrees with, or negatively responds to the post
- "pass" if the comment is neutral, asks a question, provides information without taking a stance, or doesn't clearly agree/disagree

Respond with ONLY one word: agree, disagree, or pass"""

        try:
            response = self._client.chat.completions.create(
                model=self._config.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that classifies comment stances."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=10,
            )
            
            result = response.choices[0].message.content or "pass"
            result = result.strip().lower()
            
            if result.startswith("agree"):
                return "agree"
            elif result.startswith("disagree"):
                return "disagree"
            else:
                return "pass"
                
        except Exception as e:
            return "pass"

