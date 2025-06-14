FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# 질문 없이 설치를 진행하기 위한 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive

# 작업 디렉토리 설정
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*
COPY ./scripts/download_model.py ./scripts/download_model.py
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


RUN python scripts/download_model.py


RUN playwright install --with-deps

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"] 