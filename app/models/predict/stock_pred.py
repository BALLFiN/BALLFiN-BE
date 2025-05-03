from graph_classification import classify_news_document
from scenario import A, B, C
## 자동 크롤러로 뉴스 감지 후 가져오기 임포트

temp_news = """ """

info = classify_news_document(temp_news)
classification = info['classification_result']['category']

if classification == 'A':
    A.run(temp_news)
elif classification == 'B':
    B.run(temp_news)
elif classification == 'C':
    C.run(temp_news)
else:
    print("해당 카테고리에 대한 처리가 없습니다.")
    
