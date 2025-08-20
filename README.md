# 🤖 Breifit AI Repository

본 프로젝트는 여러 국내외 뉴스 사이트에서 기사를 수집하고, AI를 활용하여 편향성이 제거된 사실 기반의 요약 뉴스를 생성하는 것을 목표로 합니다. 사용자는 다양한 관점의 뉴스를 종합적으로 이해하고, 핵심 정보를 빠르게 파악할 수 있습니다.

## 🚀 주요 기능

-   **다중 소스 기사 수집**: 설정 파일 기반으로 여러 뉴스 사이트에서 원하는 카테고리의 기사를 자동으로 수집합니다.
-   **유사 기사 그룹핑**: 내용이 유사한 기사들을 하나의 그룹으로 묶어 동일한 사건에 대한 다양한 시각을 제공합니다.
-   **AI 기반 요약**: 그룹화된 기사들을 바탕으로 핵심 내용을 담은 요약문을 생성합니다. 이 때, 편향성을 제거하여 중립적인 단어를 사용하도록 1차적으로 처리를 진행합니다.
-   **편향,공격적인 단어 제거**: 단어 대체 방식을 이용해 편향되거나 공격적인 단어들을 제거합니다.

## 🛠️ 기술 스택

-   **언어**: Python 3.10.16
-   **데이터 수집**: `aiohttp`, `BeautifulSoup`
-   **설정 관리**: `PyYAML`

## ⚙️ 실행 방법

### 1. 환경 설정
```bash
# 1. 저장소 클론
git clone https://github.com/capstone-btd/Breifit_AI.git
cd Breifit_AI

# 2. 가상환경 생성 및 활성화 (권장)
conda create -n breifit python=3.10.16
conda activate breifit

# 3. 의존성 패키지 설치
pip install -r requirements.txt
```

### 2. 실행 스크립트

프로젝트는 크게 2가지의 플로우로 구성되어 있고, 두가지의 플로우는 아래와 같이 실행하실 수 있습니다.
```bash
# 1. Wordcloud
cd WorldCloud_API
uvicorn main.py --reload
cd ../Article_Collector
python run_wc_pipeline.py

# 2. Article Collection for Breifit
cd Article_Collector
python run_full_pipeline.py
```

## 🤝 기여 방법

프로젝트에 기여하고 싶으신 분은 언제든지 이슈를 생성하거나 Pull Request를 보내주세요.

## 📄 라이선스

본 프로젝트는 [MIT 라이선스](LICENSE)를 따릅니다.
