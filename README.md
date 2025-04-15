# BALLFiN-BE
BALLFiN 백엔드 Repo

## requirements
pip install -r requirements.txt

## run backend server
uvicorn app.main:app --reload

## run test llm server
uvicorn app.models.llm.main:app_chat --host 0.0.0.0 --port 5001
& Go Live test.html



## 예외 사항
vectorDB 사용시 환경에서 c++ 빌더 요구됨 