import re
from typing import List, Dict, Any, Set
from transformers import pipeline
import os

_AI_DETECTOR = None
HTML_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
HTML_TAG_RE = re.compile(r'<[^>]+>')
SEPARATOR_RE = re.compile(r'[_=\-\*]{3,}')
NON_PROSE_RE = re.compile(r'[^a-zA-Z0-9\s\.\,\!\?\'\"\-\:\;]')

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

def _get_ai_detector():
    global _AI_DETECTOR
    if _AI_DETECTOR is None:
        # Caches model locally after first download
        if _AI_DETECTOR is None:
            _AI_DETECTOR = pipeline(
                "text-classification",
                model="coai/roberta-ai-detector-v2",
                tokenizer="coai/roberta-ai-detector-v2",
                token=os.environ.get("HF_TOKEN")
            )
    return _AI_DETECTOR

def _clean_text_for_ai_detection(raw_text: str):
    if not raw_text:
        return ""
    text = HTML_COMMENT_RE.sub(' ', raw_text)
    text = HTML_TAG_RE.sub(' ', text)
    text = SEPARATOR_RE.sub(' ', text)
    text = NON_PROSE_RE.sub(' ', text)
    cleaned_text = ' '.join(text.split())

    return cleaned_text.strip()

def detect_ai_content(student_answer: str):
    if not student_answer:
        return 0.0

    cleaned_answer = _clean_text_for_ai_detection(student_answer)
    print(f"\n[AI DETECTOR DEBUG] Cleaned Length: {len(cleaned_answer)}")
    print(f"[AI DETECTOR DEBUG] Cleaned Start: {repr(cleaned_answer[:1500])}\n")
    if len(cleaned_answer) < 30:
        return 0.0

    try:
        detector = _get_ai_detector()
        
        # If text fits in 1500 chars, evaluate directly
        if len(cleaned_answer) <= 1500:
            snippets = [cleaned_answer]
        else:
            # Create overlapping chunks of 1200 chars
            snippets = [
                cleaned_answer[i:i+1200] 
                for i in range(0, len(cleaned_answer), 800)
            ]

        max_ai_score = 0.0
        for snippet in snippets:
            results = detector(snippet, top_k=None)
            if results and isinstance(results, list):
                scores = results[0] if isinstance(results[0], list) else results
                for item in scores:
                    if str(item.get('label', '')).lower() == 'ai':
                        ai_score = float(item.get('score', 0.0)) * 100.0
                        if ai_score > max_ai_score:
                            max_ai_score = ai_score

        return round(max_ai_score, 2)
    except Exception as e:
        print(f"AI Detection Error: {e}")
        return 0.0