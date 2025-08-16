# BALLFiN-BE
BALLFiN 백엔드 Repo

## requirements
# 윈도우
pip install -r requirement/window_requirements.txt

# 리눅스
pip install -r requirement/ubuntu_requirements.txt

## run backend server
uvicorn app.main:app --reload

## 크로마 데이터베이스
github에 올려져있지 않음.
raw 데이터로 직접 구축 또는 전달받아야함

## 예외 사항
vectorDB 사용시 환경에서 c++ 빌더 요구됨 