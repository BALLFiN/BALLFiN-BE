import os
from dotenv import load_dotenv

# .env 파일 로딩
load_dotenv()

# 환경변수에서 읽기
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash-latest")
VECTORDB_PATH = os.getenv("VECTORDB_PATH", "chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")