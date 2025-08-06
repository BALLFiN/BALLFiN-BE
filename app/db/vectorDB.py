from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from pathlib import Path
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import pandas as pd


BASE_DIR = Path(__file__).parent.parent.parent.resolve()  # main.py에서 프로젝트 루트로
print(f"프로젝트 루트 디렉터리: {BASE_DIR}")
CSV_DIR = BASE_DIR / "app/db/vectorDB_Docs/news_vec"
INDEX_DIR = str(BASE_DIR / "chroma_db")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def init_vectordb():
    """
    벡터 DB를 로드하거나 새로 생성합니다.
    오류 발생 시 None을 반환합니다.
    """
    print("🔄 벡터 DB 초기화 중...")
    try:
        embedder = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
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


def build_rag_index():
    # 0) CSV 디렉터리 확인
    if not CSV_DIR.exists() or not CSV_DIR.is_dir():
        print(f"❌ CSV 디렉터리를 찾을 수 없습니다: {CSV_DIR}")
        return

    # 1) 폴더 내 모든 CSV 파일 수집
    csv_files = list(CSV_DIR.glob("*.csv"))
    if not csv_files:
        print(f"⚠️ '{CSV_DIR}' 안에 .csv 파일이 없습니다.")
        return

    all_docs = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            print(f"⚠️ 파일 로드 실패 ({csv_file.name}): {e}")
            continue

        # content 컬럼 결측 제거, metadata에 파일명 추가
        df = df.dropna(subset=["content"])
        docs = [
            Document(
                page_content=row["content"],
                metadata={
                    "title": row.get("title", ""),
                    "date": row.get("date", ""),
                    "source": csv_file.name
                }
            )
            for _, row in df.iterrows()
        ]
        if docs:
            print(f"Loaded {csv_file.name}: {len(docs)} docs")
            all_docs.extend(docs)

    if not all_docs:
        print("⚠️ 처리할 문서가 하나도 없습니다.")
        return

    # 2) 전체 문서를 한 번에 청크 분할
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunked = splitter.split_documents(all_docs)
    if not chunked:
        print("⚠️ 분할된 청크가 없습니다. CSV 내용을 확인하세요.")
        return

    # 3) 인덱스에 추가
    vectordb.add_documents(chunked)
    print(f"✅ RAG 인덱스 생성 완료: {len(chunked)} 청크 저장됨")

# ————————————————————————

# 스크립트 첫 실행 시 인덱스 없으면 생성
if vectordb._collection.count() == 0:
    print(f"❗️ 인덱스 폴더 '{INDEX_DIR}'가 비어 있습니다. 새로 생성합니다.")
    build_rag_index()
else:
    # 이미 존재하면 로드만 하면 됩니다 (Chroma 래퍼가 자동으로 로드)
    print(f"✅ 인덱스 폴더 '{INDEX_DIR}'를 로드했습니다.")