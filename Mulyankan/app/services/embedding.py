from sentence_transformers import SentenceTransformer

#Loading model instance in memory once per process
_MODEL = None

def get_embedding_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer('all-MiniLM-L6-v2')
    return _MODEL

def get_embedding(text: str):
    model = get_embedding_model()
    return model.encode(text).tolist()