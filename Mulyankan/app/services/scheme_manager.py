import json
from pathlib import Path
from django.conf import settings
from typing import List, Dict, Any
import re

SCHEMES_FILE = settings.BASE_DIR / 'data' / 'assignment_schemes.json'

def load_schemes():
    if not SCHEMES_FILE.exists():
        SCHEMES_FILE.parent.mkdir(parents=True, exist_ok=True)
        SCHEMES_FILE.write_text("{}", encoding="utf-8")
        return {}
    
    try:
        with open(SCHEMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted scheme file syntax: {e}") from e

def save_course_scheme(course_code: str, total_marks: float, questions: dict):
    schemes = load_schemes()
    formatted_questions = {}

    for q_num, q_data in questions.items():
        canonical_key = normalize_q_num(q_num)
        formatted_questions[canonical_key] = {
            "max_marks": float(q_data.get("max_marks", 0.0)),
            "question_text": str(q_data.get("question_text", "")).strip()
        }

    schemes[course_code.upper()] = {
        "total_marks": total_marks,
        "questions": formatted_questions
    }

    with open(SCHEMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(schemes, f, indent=4)

def get_question_data(course_data: dict, q_num: str):
    canonical_key = normalize_q_num(q_num)
    q_entry = course_data.get("questions", {}).get(canonical_key, {})

    return {
        "max_marks": float(q_entry.get("max_marks", 0.0)),
        "question_text": str(q_entry.get("question_text", "")).strip()
    }

def get_question_max_marks(course_data: dict, q_num: str, default: float = 0.0):
    data = get_question_data(course_data, q_num)
    return data.get("max_marks", default)

def get_question_text(course_data: dict, q_num: str, default: str = ""):
    data = get_question_data(course_data, q_num)
    return data.get("question_text", default)

def normalize_q_num(q_str: str):
    cleaned = re.sub(r'[\(\)\.\:\-\s]+', '', str(q_str)).lower()
    return cleaned

def decompose_submission_qa(markdown_text: str, course_code: str = "") -> List[Dict[str, Any]]:
    #Captures question number and student answer body
    q_header_pattern = re.compile(
        r'^\s*(?:#+\s*)?[\*\_]*(?:Q|Question)\s*\.?\s*'
        r'(\d+(?:\s*\.?\s*\(?[a-zA-Z0-9]+\)?)?)'
        r'[\)\.\:\-\s\*\_]*',
        re.IGNORECASE | re.MULTILINE
    )

    answer_block_pattern = re.compile(
        r'Ans(?:wer)?(?:\s*\(do\s+not\s+edit\s+this\s+cell\))?',
        re.IGNORECASE
    )

    matches = list(q_header_pattern.finditer(markdown_text))
    qa_units = []

    schemes = load_schemes()
    course_data = schemes.get(course_code.upper(), {})

    for i, match in enumerate(matches):
        raw_q_num = match.group(1).strip()
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)

        block_text = markdown_text[start_pos:end_pos]

        ans_marker = answer_block_pattern.search(block_text)
        if ans_marker:
            ans_body = block_text[ans_marker.end():].strip()

        canonical_q_num = normalize_q_num(raw_q_num)
        max_marks = get_question_max_marks(course_data, canonical_q_num, default=0.0)
        q_text = get_question_text(course_data, canonical_q_num, default="")

        qa_units.append({
                    "question_number": raw_q_num,
                    "canonical_number": canonical_q_num, 
                    "max_marks": max_marks,
                    "question_text": q_text,
                    "student_answer": ans_body,
                })

    return qa_units