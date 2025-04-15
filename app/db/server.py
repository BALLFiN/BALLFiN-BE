# server.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# 크롤러와 벡터 DB 관리자 임포트
from crawler import NaverNewsCrawler
from vectorDB import VectorDBManager

# FastAPI 앱 생성
app = FastAPI(title="뉴스 벡터 데이터베이스 API")

# 벡터 데이터베이스 관리자 초기화
db_manager = VectorDBManager(persist_directory="./chroma_db")

# 크롤러 초기화
crawler = NaverNewsCrawler(headless=True)

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 크롤러 종료"""
    crawler.close()

@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {"status": "running", "message": "뉴스 벡터 데이터베이스 API가 실행 중입니다."}

@app.post("/update_news")
async def update_news(request: Request):
    """
    뉴스를 크롤링하고 벡터 데이터베이스를 업데이트합니다.
    
    Request:
    {
        "keyword": "검색 키워드",
        "max_articles": 최대 수집할 기사 수
    }
    """
    data = await request.json()
    keyword = data.get('keyword', '삼성전자')
    max_articles = data.get('max_articles', 50)
    
    # 뉴스 크롤링
    news_df = crawler.crawl_news(keyword=keyword, max_articles=max_articles)
    
    if news_df.empty:
        return JSONResponse(content={"status": "error", "message": "No news found"})
    
    # Document 객체로 변환
    documents = crawler.to_documents(news_df)
    
    # 벡터 데이터베이스 업데이트
    db_manager.create_or_update_db(documents)
    
    return JSONResponse(content={
        "status": "success", 
        "message": f"Updated news database with {len(documents)} articles"
    })

@app.get("/get_documents")
async def get_documents(query: str, k: int = 3):
    """
    쿼리와 관련된 문서를 벡터 데이터베이스에서 검색합니다.
    
    Args:
        query (str): 검색 쿼리
        k (int): 반환할 최대 문서 수
    """
    retriever = db_manager.get_retriever(k=k)
    if not retriever:
        raise HTTPException(status_code=500, detail="Failed to load vector database")
        
    # 문서 검색
    docs = retriever.invoke(query)
    
    # 직렬화 가능한 형식으로 변환
    results = []
    for doc in docs:
        results.append({
            "content": doc.page_content,
            "metadata": doc.metadata
        })
    
    return JSONResponse(content={
        "status": "success",
        "query": query,
        "documents": results
    })

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)