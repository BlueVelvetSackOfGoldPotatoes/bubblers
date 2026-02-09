from __future__ import annotations

from app.pipeline.providers import Voter, VoteType


class LocalVoter(Voter):
    """Sentiment-based voter using NLTK VADER. Designed for social media text."""

    def __init__(self) -> None:
        self._analyzer = None  # lazy-loaded

    def _load_analyzer(self):
        if self._analyzer is None:
            import nltk
            try:
                nltk.data.find("sentiment/vader_lexicon.zip")
            except LookupError:
                print("[local] Downloading VADER lexicon (one-time)...")
                nltk.download("vader_lexicon", quiet=True)
            from nltk.sentiment.vader import SentimentIntensityAnalyzer
            self._analyzer = SentimentIntensityAnalyzer()
        return self._analyzer

    def classify(self, post_title: str, post_body: str, comment_text: str) -> VoteType:
        try:
            analyzer = self._load_analyzer()
            scores = analyzer.polarity_scores(comment_text)
            compound = scores["compound"]
            if compound > 0.05:
                return "agree"
            elif compound < -0.05:
                return "disagree"
            else:
                return "pass"
        except Exception:
            return "pass"
