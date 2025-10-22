# BALLFiN-BE
BALLFiN 백엔드 Repo

## requirements
pip install -r requirements.txt

## run backend server
uvicorn app.main:app --reload


## 현재 크로마 데이터베이스
db 크기 문제로 row news data를 통해 직접 구축하도록함 서버 실행시 자동 구축

## 예외 사항
vectorDB 사용시 환경에서 c++ 빌더 요구됨 