import os
# Tắt các cảnh báo TensorFlow
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 0=all, 1=info, 2=warning, 3=error
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
    Mã hóa một đoạn văn bản thành vector embedding
    
    Args:
        text (str): Văn bản cần mã hóa
        model_name (str, optional): Tên của model. Mặc định là "all-MiniLM-L6-v2"
        
    Returns:
        numpy.ndarray: Vector embedding
    """

    model = get_model_embedder(model_name)
    vector = model.encode(text)
    
    return vector

def vector_to_pg_format(vector):
    """
    Chuyển đổi vector numpy thành chuỗi định dạng PostgreSQL VECTOR
    
    Args:
        vector (numpy.ndarray): Vector embedding
        
    Returns:
        str: Chuỗi định dạng '[x1,x2,x3,...]'
    """
    result = "[" + ",".join([str(float(x)) for x in vector]) + "]"
    return result