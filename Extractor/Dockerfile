FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 git 설치 (혹시 모를 의존성 대비)
RUN apt-get update && apt-get install -y git

# 의존성 파일 복사 및 설치
COPY ./requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 전체 파일 복사
# .dockerignore에 명시된 파일들은 제외됨
COPY . .

# FastAPI 애플리케이션이 실행될 포트 노출
EXPOSE 8000

# 애플리케이션 실행
# --host 0.0.0.0 은 컨테이너 외부에서 접속을 허용하기 위함
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 