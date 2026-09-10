from django.db import transaction
from app.models import AssignmentSubmission, EvaluationResult
from app.services.evaluator import decompose_submission_qa, evaluate_qa_unit
from app.services.retrieval import retrieve_relevant_chunks

def evaluate_submission_pipeline(submission_id: int) -> EvaluationResult:

    submission = AssignmentSubmission.objects.select_related("course").get(id=submission_id)
    course = submission.course

    #Parsing markdown into individual Q&A units
    qa_units = decompose_submission_qa(markdown_text=submission.extracted_text, course_code=course.course_code)

    total_score_awarded = 0.0
    total_max_marks = 0.0
    weighted_content_sum = 0.0
    weighted_presentation_sum = 0.0
    weighted_linguistic_sum = 0.0
    max_observed_plagiarism = 0.0
    question_audits = []
    feedback_segments = []

    for unit in qa_units:
        q_num = unit.get("question_number", "Unknown")
        q_text = unit.get("question_text", "")
        s_answer = unit.get("student_answer", "")
        max_marks = float(unit.get("max_marks", 0.0))

        #Retrieving textbook reference context
        retrieved_chunks = retrieve_relevant_chunks(course, q_text, top_k=3)

        #Grading
        evaluation = evaluate_qa_unit(question_text=q_text, student_answer=s_answer, max_marks=max_marks, context_chunks=retrieved_chunks)

        scores_norm = evaluation.get("scores_normalized", {})
        c_pct = float(scores_norm.get("content", 0.0))
        p_pct = float(scores_norm.get("presentation", 0.0))
        l_pct = float(scores_norm.get("linguistic", 0.0))

        weighted_content_sum += (c_pct / 100.0) * (max_marks * 0.70)
        weighted_presentation_sum += (p_pct / 100.0) * (max_marks * 0.15)
        weighted_linguistic_sum += (l_pct / 100.0) * (max_marks * 0.15)

        score_awarded = evaluation.get("score_awarded", 0.0)
        plagiarism_score = evaluation.get("plagiarism_score", 0.0)
        penalty_deducted = evaluation.get("penalty_deducted", 0.0)
        q_feedback = evaluation.get("feedback", "")

        total_score_awarded += score_awarded
        total_max_marks += max_marks
        if plagiarism_score > max_observed_plagiarism:
            max_observed_plagiarism = plagiarism_score

        feedback_segments.append(f"Q{q_num}: {q_feedback}")

        #Assembling audit data
        question_audits.append({
            "question_number": q_num,
            "max_marks": max_marks,
            "score_awarded": score_awarded,
            "scores_normalized": scores_norm,
            "plagiarism_score": plagiarism_score,
            "penalty_deducted": penalty_deducted,
            "feedback": q_feedback,
            "citations": evaluation.get("citations", []),
            "retrieved_chunks": [
                {
                    "chunk_id": c.get("chunk_id"),
                    "block_number": c.get("block_number"),
                    "unit_number": c.get("unit_number"),
                    "page_number": c.get("page_number"),
                    "similarity_score": c.get("similarity_score")
                }
                for c in retrieved_chunks
            ]
        })

    overall_feedback = (
        f"Evaluation Summary: Scored {round(total_score_awarded, 2)} out of {round(total_max_marks, 2)}.\n\n"
        + "\n\n".join(feedback_segments)
    )

    with transaction.atomic():
        evaluation_result, _ = EvaluationResult.objects.update_or_create(
            submission=submission,
            defaults={
                "score_content": round(weighted_content_sum, 2),
                "score_presentation": round(weighted_presentation_sum, 2),
                "score_linguistic": round(weighted_linguistic_sum, 2),
                "suggested_final_score": round(total_score_awarded, 2),
                "plagiarism_percentage": int(round(max_observed_plagiarism, 2)),
                "evaluator_remarks": overall_feedback,
                "audit_logic": question_audits,
            }
        )

    return evaluation_result