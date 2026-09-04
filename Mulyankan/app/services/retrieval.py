from typing import List, Dict, Any
from pgvector.django import CosineDistance
from app.models import CourseContext, Course
from app.services.embedding import get_embedding


def retrieve_relevant_chunks(course: Course, query_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Embeds the input query and retrieves top-k relevant course textbook chunks filtered strictly by course using pgvector cosine distance."""

    query_vector = get_embedding(query_text)

    #Querying CourseContext model
    context_matches = (
        CourseContext.objects.filter(course=course)
        .annotate(distance=CosineDistance('embedding', query_vector))
        .order_by('distance')[:top_k]
    )

    results = []
    for match in context_matches:
        # Distance ranges from 0 (identical) to 2 (completely opposite)
        # Cosine similarity % = (1 - distance) * 100
        similarity_pct = round(max(0.0, (1.0 - match.distance)) * 100, 2)
        
        results.append({
            "chunk_id": match.id,
            "block_number": match.block_number,
            "unit_number": match.unit_number,
            "page_number": match.page_number,
            "text_chunk": match.text_chunk,
            "similarity_score": similarity_pct
        })

    return results