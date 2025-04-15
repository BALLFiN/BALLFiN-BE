# vectordb.py
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

class VectorDBManager:
    def __init__(self, persist_directory="./chroma_db"):
        """
        벡터 데이터베이스 관리자 초기화
        
        Args:
            persist_directory (str): 벡터 데이터베이스 저장 경로
        """
        self.directory = persist_directory
        # HuggingFace 임베딩 모델 사용
        self.embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    def create_or_update_db(self, documents):
        """
        문서로부터 벡터 데이터베이스 생성 또는 업데이트
        
        Args:
            documents (list): Document 객체 리스트
            
        Returns:
            Chroma: 벡터 데이터베이스 객체
        """
        try:
            # 기존 DB 로드 시도
            existing_db = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.directory
            )
            # 기존 DB에 문서 추가
            existing_db.add_documents(documents)
            existing_db.persist()
            print(f"Updated existing database with {len(documents)} documents")
            return existing_db
        except Exception as e:
            print(f"Creating new database: {e}")
            # DB가 없으면 새로 생성
            db = Chroma.from_documents(
                documents=documents,
                embedding=self.embeddings,
                persist_directory=self.directory
            )
            db.persist()
            print(f"Created new database with {len(documents)} documents")
            return db
    
    def load_db(self):
        """
        기존 벡터 데이터베이스 로드
        
        Returns:
            Chroma: 벡터 데이터베이스 객체 또는 None (실패 시)
        """
        try:
            db = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.directory
            )
            print(f"Successfully loaded database from {self.directory}")
            return db
        except Exception as e:
            print(f"Error loading database: {e}")
            return None
            
    def get_retriever(self, search_type="similarity", k=3):
        """
        검색을 위한 리트리버 객체 반환
        
        Args:
            search_type (str): 검색 타입 (similarity, mmr 등)
            k (int): 반환할 최대 문서 수
            
        Returns:
            Retriever: 리트리버 객체 또는 None (실패 시)
        """
        db = self.load_db()
        if db:
            return db.as_retriever(search_type=search_type, search_kwargs={"k": k})
        return None

# 직접 실행 시 테스트 코드
if __name__ == "__main__":
    from langchain_core.documents import Document
    
    # 테스트용 문서 생성
    test_docs = [
        Document(
            page_content="테스트 문서 1의 내용입니다.", 
            metadata={"title": "테스트 문서 1", "source": "test"}
        ),
        Document(
            page_content="테스트 문서 2의 내용입니다.", 
            metadata={"title": "테스트 문서 2", "source": "test"}
        )
    ]
    
    # 테스트 DB 저장 경로
    test_db_path = "./test_chroma_db"
    
    # 벡터 DB 관리자 초기화 및 테스트
    db_manager = VectorDBManager(persist_directory=test_db_path)
    db_manager.create_or_update_db(test_docs)
    
    # 리트리버 테스트
    retriever = db_manager.get_retriever(k=1)
    if retriever:
        result = retriever.invoke("테스트")
        print("검색 결과:")
        for doc in result:
            print(f"- {doc.page_content}")