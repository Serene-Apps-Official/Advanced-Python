import os
import re
from collections import Counter

def _split_sentences(text: str):
    # very lightweight sentence splitter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def extractive_summary(text: str, n_sentences: int = 3) -> str:
    """Simple extractive summarizer: rank sentences by word frequency.

    This is a local fallback when no external AI key is provided.
    """
    if not text or not text.strip():
        return ""

    sentences = _split_sentences(text)
    words = re.findall(r"\w+", text.lower())
    freq = Counter(words)

    # score sentences
    scores = []
    for s in sentences:
        s_words = re.findall(r"\w+", s.lower())
        if not s_words:
            continue
        score = sum(freq[w] for w in s_words)
        scores.append((score, s))

    scores.sort(reverse=True)
    selected = [s for _, s in scores[:n_sentences]]
    return " ".join(selected)

def ai_summarize(text: str, api_key: str = None, model: str = "gemini", **kwargs) -> str:
    """Placeholder for AI summarization.

    If an API key is provided you can implement a call to Gemini/OpenAI here.
    For now this function falls back to extractive_summary if no key is present.
    """
    if api_key:
        # The actual integration with Gemini must be provided by the user. This
        # placeholder shows where to add the call (requests or official SDK).
        raise NotImplementedError("AI summarization using Gemini is not implemented in this stub.\n"
                                  "Set GEMINI_API_KEY and implement the network call in ai_data_analyzer.summarizer.ai_summarize.")

    return extractive_summary(text, kwargs.get("n_sentences", 3))
