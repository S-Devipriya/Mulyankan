import re
from typing import List, Dict, Any, Set

def get_word_ngrams(text: str, n: int = 4) -> Set[tuple]:
    words = re.findall(r'\b\w+\b', text.lower())
    if len(words) < n:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i+n]) for i in range(len(words) - n + 1)}

def compute_textbook_overlap(student_answer: str, context_chunks: List[Dict[str, Any]], n: int = 4):
    student_ngrams = get_word_ngrams(student_answer, n=n)
    if not student_ngrams:
        return 0.0

    chunk_ngrams = set()
    for chunk in context_chunks:
        text = chunk.get("text_chunk", "")
        if text:
            chunk_ngrams.update(get_word_ngrams(text, n=n))

    if not chunk_ngrams:
        return 0.0

    matched_ngrams = student_ngrams.intersection(chunk_ngrams)
    overlap_pct = (len(matched_ngrams) / len(student_ngrams)) * 100.0

    return round(overlap_pct, 2)