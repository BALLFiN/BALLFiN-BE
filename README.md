# BALLFiN-BE
BALLFiN 백엔드 Repo

## requirements
pip install -r requirements.txt

## run backend server
uvicorn app.main:app --reload

## run test llm server
uvicorn app.models.llm.main:app_chat --host 0.0.0.0 --port 5001
& Go Live test.html

## run test crawler server
python app/db/test.py

## 현재 크로마 데이터베이스
5가지 키워드로 1000개 데이터 저장

## 예외 사항
vectorDB 사용시 환경에서 c++ 빌더 요구됨 