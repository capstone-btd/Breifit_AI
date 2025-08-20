# 1. 기본 이미지를 Playwright 공식 이미지로 변경 (업데이트된 버전)
FROM mcr.microsoft.com/playwright/python:v1.53.0-jammy

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. requirements.txt 복사 및 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. 소스 코드 복사
COPY . .

# 5. Cloud Run이 사용할 포트 설정
ENV PORT 8080
EXPOSE 8080

# 6. 애플리케이션 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]