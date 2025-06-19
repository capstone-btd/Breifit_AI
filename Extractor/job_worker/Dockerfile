# 베이스 이미지 설정
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 의존성 설치 (Playwright를 위해 build-essential 등 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install --with-deps chromium

# 애플리케이션 파일 복사
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
COPY DB ./DB
COPY models ./models
COPY run_full_pipeline.py .
# COPY pipeline_for_local.py .

# 실행할 기본 명령어 설정
CMD ["python", "run_full_pipeline.py"] 