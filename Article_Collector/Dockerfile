# 1. GPU 지원 및 빌드 환경을 위해 NVIDIA CUDA devel 이미지를 기본으로 설정
# CUDA 12.1.1, cuDNN 8, Ubuntu 22.04 기반의 개발자용 이미지
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 환경 변수 설정 (non-interactive apt-get)
ENV DEBIAN_FRONTEND=noninteractive

# 4. Python 3.11 설치
# deadsnakes PPA를 추가하여 Python 3.11을 설치합니다.
# build-essential은 베이스 이미지에 이미 포함되어 있습니다.
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# 5. python과 python3가 python3.11을 가리키도록 기본값 변경
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# 6. pip 업그레이드
RUN python3 -m pip install --no-cache-dir --upgrade pip

# 7. requirements.txt 복사 및 의존성 설치 (캐시 활용)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 8. API 키를 환경 변수로 설정
ENV GEMINI_API_KEY="직접 입력"

# 9. 소스 코드 복사
COPY . .

# 10. 기본 실행 명령어 설정
CMD ["python3", "run_full_pipeline.py"] 