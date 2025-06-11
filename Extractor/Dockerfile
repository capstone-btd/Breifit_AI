FROM python:3.10-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 git 설치 (이미지 크기 최적화를 위해 캐시 정리)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사 및 설치
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 프로젝트 전체 파일 복사
# .dockerignore에 명시된 파일들은 제외됨
COPY . .

# Cloud Run의 기본 포트인 8080번 포트 노출
EXPOSE 8080

# 애플리케이션 실행
# uvicorn의 포트를 8080으로 고정합니다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 