import re
import os
import json
from google import genai
from google.genai import types
from typing import List, Dict, Any
import app.services.scheme_manager
from app.services.plagiarism_checker import compute_textbook_overlap, detect_ai_content

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        
def evaluate_qa_unit(question_text: str, student_answer: str, max_marks: float, context_chunks: List[Dict[str, Any]], peer_plagiarism_score: float = 0.0, peer_matches: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    #Evaluates a student's question-answer pair and returns scoring and audit_trail

    formatted_context = ""
    for idx, chunk in enumerate(context_chunks, 1):
        formatted_context += (
            f"--- Context Excerpt [{idx}] (Block {chunk['block_number']}, "
            f"Unit {chunk['unit_number']}, Page {chunk['page_number']}) ---\n"
            f"{chunk['text_chunk']}\n\n"
        )

    system_instruction = (
        "You are an academic evaluation engine for university assignment grading. "
        "Evaluate the student's answer strictly based on accuracy, relevance, and alignment "
        "with the provided course textbook context.\n\n"
        "Rate each criterion on an absolute scale of 0 to 100:\n"
        "- Content (0-100): Conceptual correctness, factual accuracy, and alignment with course material.\n"
        "- Presentation (0-100): Logical organization, flow, formatting, and structural clarity.\n"
        "- Linguistic (0-100): Academic language, grammar, clarity, and terminological precision.\n\n"
        "Do NOT compute total marks or perform arithmetic. Provide qualitative feedback and cite specific "
        "textbook blocks, units, and pages that substantiate your evaluation."
    )

    prompt = f"""
        QUESTION:
        {question_text}
        OFFICIAL REFERENCE TEXTBOOK CHUNKS:
        {formatted_context if formatted_context else "No specific textbook chunk retrieved."}
        STUDENT ANSWER:
        {student_answer}
        Provide an objective assessment of the student answer in the requested JSON format following the 0-100 rubric criteria and referencing citations."""

    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "scores_normalized": {
                        "type": "OBJECT",
                        "properties": {
                            "content": {"type": "NUMBER", "description": "Score 0-100 for conceptual correctness"},
                            "presentation": {"type": "NUMBER", "description": "Score 0-100 for organization and clarity"},
                            "linguistic": {"type": "NUMBER", "description": "Score 0-100 for academic language"}
                        },
                        "required": ["content", "presentation", "linguistic"]
                    },
                    "feedback": {
                        "type": "STRING", 
                        "description": "Question-specific feedback identifying conceptual strengths, gaps, and areas for improvement"
                    },
                    "citations": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "block_number": {"type": "INTEGER"},
                                "unit_number": {"type": "INTEGER"},
                                "page_number": {"type": "INTEGER"},
                                "relevance_rationale": {"type": "STRING"}
                            },
                            "required": ["block_number", "unit_number", "page_number", "relevance_rationale"]
                        }
                    }
                },
                "required": ["scores_normalized", "feedback", "citations"]
            },
            temperature=0.2
        )
    )

    try:
        data = json.loads(response.text)
    except Exception as e:
        print(f"[EVALUATOR ERROR] Gemini API generation failed: {e}")
        raise e

    #Calculating actual scores as per rubric: content (70%), presentaion and linguistic accuracy (15%) each
    scores = data.get("scores_normalized", {})
    c_score = max(0.0, min(100.0, float(scores.get("content", 0.0))))
    p_score = max(0.0, min(100.0, float(scores.get("presentation", 0.0))))
    l_score = max(0.0, min(100.0, float(scores.get("linguistic", 0.0))))

    weighted_pct = (0.70 * c_score) + (0.15 * p_score) + (0.15 * l_score)
    base_score = (weighted_pct / 100.0) * max_marks

    #Computing linear proportional text-book/peer plagiarism penalty for lexical similarity > 70%
    textbook_plagiarism_score = compute_textbook_overlap(student_answer, context_chunks)
    effective_plagiarism_score = max(textbook_plagiarism_score, peer_plagiarism_score)

    penalty_factor = 0.0
    if effective_plagiarism_score > 70.0:
        penalty_factor = min(1.0, (effective_plagiarism_score - 70.0) / (100.0 - 70.0))

    ai_plagiarism_score = detect_ai_content(student_answer)

    final_score = base_score * (1.0 - penalty_factor)
    final_score = round(max(0.0, min(max_marks, final_score)), 2)

    return {
        "scores_normalized": {
            "content": c_score,
            "presentation": p_score,
            "linguistic": l_score
        },
        "score_awarded": final_score,
        "textbook_plagiarism_score": textbook_plagiarism_score,
        "ai_plagiarism_score": ai_plagiarism_score,
        "peer_plagiarism_score": peer_plagiarism_score,
        "peer_matches": peer_matches,
        "penalty_deducted": round(base_score * penalty_factor, 2),
        "feedback": data.get("feedback", ""),
        "citations": data.get("citations", [])
    }