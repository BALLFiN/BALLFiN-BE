from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from app.models.llm.config import VECTORDB_PATH, EMBEDDING_MODEL

# 데이터베이스 로딩 함수
def load_vectordb():
    """저장된 Chroma VectorDB를 로드합니다."""
    try:
        embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        vectordb = Chroma(
            persist_directory=VECTORDB_PATH,
            embedding_function=embeddings
        )
        print(f"✅ 벡터 데이터베이스를 '{VECTORDB_PATH}'에서 성공적으로 로드했습니다.")
        return vectordb
    except Exception as e:
        import traceback
        print("❌ VectorDB 로딩 중 예외 발생!")
        traceback.print_exc()
        print(f"에러 내용: {e}")
        return None
