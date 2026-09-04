import re
from typing import List, Dict, Any
import app.services.scheme_manager

def decompose_submission_qa(markdown_text: str, course_code: str = "") -> List[Dict[str, Any]]:
    #Captures question number, question text and student answer body
    qa_pattern = re.compile(
        r'(?:^|\n)\s*'
        r'(?:Q|Question)?\s*[\.\:\-]?\s*'
        r'(\d+\s*(?:\([a-zA-Z0-9]+\)|[a-zA-Z]|\.\d+)?)'
        r'[\.\:\-\s]+'
        r'(.*?)\s*'
        r'(?:\n|\s+)(?:Ans(?:wer)?[\s\:\.\-]+)\s*'
        r'([\s\S]*?)'
        r'(?=(?:\n\s*(?:Q|Question)?\s*[\.\:\-]?\s*\d+\s*(?:\([a-zA-Z0-9]+\)|[a-zA-Z]|\.\d+)?[\.\:\-\s]+(?:Ans(?:wer)?|\w))|\Z)',
        re.IGNORECASE
    )

    qa_units = []
    schemes = app.services.scheme_manager.load_schemes()
    course_data = schemes.get(course_code.upper(), {})

    for match in qa_pattern.finditer(markdown_text):
        raw_q_num = match.group(1).strip()
        q_text = match.group(2).strip()
        ans_body = match.group(3).strip()

        #Cleaning formatting
        q_text = re.sub(r'\s+', ' ', q_text)
        q_text = re.sub(r'\(\s*\d+\s*marks?\s*\)', '', q_text, flags=re.IGNORECASE).strip()

        #Normalizing question number for looking up in assignment_schemes.json
        canonical_q_num = app.services.scheme_manager.normalize_q_num(raw_q_num)
        max_marks = app.services.scheme_manager.get_question_max_marks(course_data, canonical_q_num, default=20.0)

        qa_units.append({
            "question_number": raw_q_num,
            "canonical_number": canonical_q_num, 
            "max_marks": max_marks,
            "question_text": q_text,
            "student_answer": ans_body,
            #audit_trail placeholders to be updated later
            "scores_normalized": {
                "content": 0.0,
                "presentation": 0.0,
                "linguistic": 0.0
            },
            "score_awarded": 0.0,
            "feedback": "",
            "citations": []
        })

    return qa_units