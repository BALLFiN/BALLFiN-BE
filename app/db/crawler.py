# crawler.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from urllib.parse import quote
from langchain_core.documents import Document

class NaverNewsCrawler:
    def __init__(self, headless=True):
        # 셀레니움 설정
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 로컬 환경에서 ChromeDriver 자동 설치
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
    
    def crawl_news(self, keyword="삼성전자", max_articles=100):
        """
        네이버 뉴스를 크롤링하고 결과를 DataFrame으로 반환합니다.
        
        Args:
            keyword (str): 검색할 키워드
            max_articles (int): 최대 수집할 기사 수
            
        Returns:
            pd.DataFrame: 수집된 뉴스 데이터
        """
        encoded = quote(keyword)
        base_url = f"https://search.naver.com/search.naver?where=news&query={encoded}&start="

        articles = []
        page = 1

        while len(articles) < max_articles:
            start = (page - 1) * 10 + 1
            url = base_url + str(start)
            self.driver.get(url)
            time.sleep(2)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            news_blocks = soup.select("div.news_area")

            if not news_blocks:
                print(f"No news found on page {page}")
                break

            for block in news_blocks:
                title_tag = block.select_one("a.news_tit")
                summary_tag = block.select_one("a.dsc_txt_wrap") or block.select_one("div.dsc_wrap span")
                date_tag = block.select_one("div.info_group span")

                if title_tag and date_tag:
                    title = title_tag.get("title")
                    link = title_tag.get("href")
                    summary = summary_tag.get_text() if summary_tag else ""
                    date = date_tag.get_text()

                    # ✅ 제목 또는 요약 내용에 키워드 포함 여부 검사
                    if keyword in title or keyword in summary:
                        articles.append({
                            "title": title,
                            "link": link,
                            "summary": summary,
                            "date": date
                        })

                    if len(articles) >= max_articles:
                        break

            print(f"Page {page} done, total collected: {len(articles)}")
            page += 1

        df = pd.DataFrame(articles)

        # 날짜 정렬 처리
        def parse_date(text):
            try:
                return pd.to_datetime(text)
            except:
                return text

        if not df.empty:
            df["parsed_date"] = df["date"].apply(parse_date)
            df = df.sort_values(by="parsed_date", ascending=False).reset_index(drop=True)
            df.drop(columns=["parsed_date"], inplace=True)

        return df
    
    def to_documents(self, dataframe):
        """
        DataFrame을 LangChain Document 객체로 변환합니다.
        
        Args:
            dataframe (pd.DataFrame): 뉴스 데이터가 포함된 DataFrame
            
        Returns:
            list: Document 객체 리스트
        """
        documents = []
        for _, row in dataframe.iterrows():
            # Combine title and summary for the document's content
            content = f"제목: {row['title']}\n요약: {row['summary']}\n날짜: {row['date']}"
            doc = Document(
                page_content=content, 
                metadata={
                    "title": row['title'], 
                    "date": row['date'], 
                    "link": row['link'],
                    "source": "naver_news",
                    "topic": row['title'][:20]  # Using first 20 chars of title as topic
                }
            )
            documents.append(doc)
        return documents
    
    def close(self):
        """WebDriver를 종료합니다."""
        if hasattr(self, 'driver'):
            self.driver.quit()

# 직접 실행 시 테스트 코드
if __name__ == "__main__":
    crawler = NaverNewsCrawler(headless=True)
    try:
        print("뉴스 크롤링 시작...")
        df = crawler.crawl_news(keyword="인공지능", max_articles=10)
        print(f"수집된 기사 수: {len(df)}")
        print(df.head())
        
        # Document 변환 테스트
        docs = crawler.to_documents(df)
        print(f"변환된 Document 수: {len(docs)}")
        if docs:
            print("첫 번째 Document 내용:")
            print(docs[0].page_content)
            print("메타데이터:", docs[0].metadata)
    finally:
        crawler.close()