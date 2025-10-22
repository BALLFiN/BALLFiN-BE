from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path
from langchain.schema import Document
import pandas as pd
import re


BASE_DIR = Path(__file__).parent.parent.parent.resolve()  # main.py에서 프로젝트 루트로
print(f"프로젝트 루트 디렉터리: {BASE_DIR}")
CSV_DIR = BASE_DIR / "app/db/news_vec"
INDEX_DIR = str(BASE_DIR / "chroma_db")
# EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_MODEL = "exp-models/dragonkue-KoEn-E5-Tiny"


def init_vectordb():
    """
    벡터 DB를 로드하거나 새로 생성합니다.
    오류 발생 시 None을 반환합니다.
    """
    print("🔄 벡터 DB 초기화 중...")
    try:  
        embedder = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": True}  
            )
        db = Chroma(
            persist_directory=INDEX_DIR,
            embedding_function=embedder
        ) 
        print("✅ 벡터 DB 로드 완료")
        return db
    except Exception as e:
        print(f"❌ 벡터 DB 로드 실패: {e}")
        return None

# 전역 벡터 DB 초기화
vectordb = init_vectordb() 

if vectordb is None:
    # vectordb가 없으면 이후 작업이 무의미하므로 종료
    raise SystemExit("벡터 DB 초기화에 실패하여 프로그램을 종료합니다.")


def chunk_text(text: str, max_chars: int = 500, min_chars: int = 100):
    # 문장 단위 분할
    sentences = re.split(r'(?<=[.!?])\s+(?=[가-힣A-Z])', str(text).strip())
    chunks = []
    temp_chunk = ""

    for sent in sentences:
        if len(temp_chunk) + len(sent) <= max_chars:
            temp_chunk += " " + sent
        else:
            if temp_chunk.strip():
                chunks.append(temp_chunk.strip())
            temp_chunk = sent

    if temp_chunk.strip():
        # 마지막 청크가 너무 짧으면 이전과 합침
        if chunks and len(temp_chunk) < min_chars:
            chunks[-1] += " " + temp_chunk
        else:
            chunks.append(temp_chunk.strip())

    return chunks



def build_rag_index():

    if not CSV_DIR.exists() or not CSV_DIR.is_dir():
        print(f"❌ CSV 디렉터리를 찾을 수 없습니다: {CSV_DIR}")
        return

    csv_files = list(CSV_DIR.glob("*.csv"))
    if not csv_files:
        print(f"⚠️ '{CSV_DIR}' 안에 .csv 파일이 없습니다.")
        return

    all_docs = []
    for csv_file in csv_files:
        
        try:
            df = pd.read_csv(csv_file)
            df.dropna(subset=["link_url"], inplace=True)

        except Exception as e:
            print(f"⚠️ 파일 로드 실패 ({csv_file.name}): {e}")
            continue
        chunk_size = 0
        for _, row in df.iterrows():
            doc_id = row['link_url']# 또는 고유 해시
            chunks = chunk_text(row["content"], max_chars=500, min_chars=100)
            for chunk in chunks:
                metadata = {
                    "doc_id": doc_id,
                    "title": row.get("title", ""),
                    "date": row.get("date", ""),
                    "link": row.get("link_url", ""),
                    "corp": row.get("corp", ""),
                    "impact_score": row.get("impact_score", 0)
                }
                all_docs.append(Document(page_content=chunk, metadata=metadata))
            chunk_size += len(chunks)
        print(f"Loaded {csv_file.name}: {chunk_size} docs (after splitting)")

    if not all_docs:
        print("⚠️ 처리할 문서가 하나도 없습니다.")
        return
    
    for i in range(0, len(all_docs), 500):
        batch = all_docs[i:i+500]
        vectordb.add_documents(batch)

    print(f"✅ RAG 인덱스 생성 완료: {len(all_docs)} 문서/청크 저장됨")


# ————————————————————————
#build_rag_index()
#스크립트 첫 실행 시 인덱스 없으면 생성


if vectordb._collection.count() == 0:
    print(f"❗️ 인덱스 폴더 '{INDEX_DIR}'가 비어 있습니다. 새로 생성합니다. 좀걸림 ㄱㄷㄱㄷ")
    build_rag_index()
else:
    # 이미 존재하면 로드만 하면 됩니다 (Chroma 래퍼가 자동으로 로드)
    print(f"✅ 인덱스 폴더 '{INDEX_DIR}'를 로드했습니다.")