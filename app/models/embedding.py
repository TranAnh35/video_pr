import os
from sentence_transformers import SentenceTransformer

# Singleton pattern cho model embedding
_model_instance = None

def get_model_embedder(model_name="all-MiniLM-L6-v2"):
    global _model_instance
    if _model_instance is None:
        print(f"Loading embedding model: {model_name}")
        _model_instance = SentenceTransformer(model_name)
        print("Model loaded successfully")
    return _model_instance

def encode_text(text, model_name="all-MiniLM-L6-v2"):
    """
    Encode a text into vector embedding
    
    Args:
        text (str): Text to encode
        model_name (str, optional): Name of the model. Default is "all-MiniLM-L6-v2"
        
    Returns:
        numpy.ndarray: Vector embedding
    """

    model = get_model_embedder(model_name)
    vector = model.encode(text)
    
    return vector

def vector_to_pg_format(vector):
    """
    Convert numpy vector to PostgreSQL VECTOR format
    
    Args:
        vector (numpy.ndarray): Vector embedding
        
    Returns:
        str: String in PostgreSQL VECTOR format '[x1,x2,x3,...]'
    """
    result = "[" + ",".join([str(float(x)) for x in vector]) + "]"
    return result