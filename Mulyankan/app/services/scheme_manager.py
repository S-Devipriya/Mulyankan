import json
from pathlib import Path
from django.conf import settings
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
    schemes[course_code.upper()] = {
        "total_marks": total_marks,
        "questions": {str(k): float(v) for k, v in questions.items()}
    }
    with open(SCHEMES_FILE, 'w', encoding='utf-8') as f:
        json.dump(schemes, f, indent=4)

def get_question_max_marks(course_data: dict, q_num: str, default: float = 20.0):
    return float(course_data.get("questions", {}).get(str(q_num), default))

def normalize_q_num(q_str: str):
    cleaned = re.sub(r'[\(\)\.\:\-\s]+', '', str(q_str)).lower()
    return cleaned