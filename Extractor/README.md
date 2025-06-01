# 뉴스 기사 분석 및 요약 프로젝트

본 프로젝트는 여러 국내외 뉴스 사이트에서 기사 데이터를 수집하고, 이를 분석하여 최종적으로 편향성이 제거된 사실 기반의 AI 요약 뉴스를 생성하는 것을 목표로 합니다.

## 현재까지 구현된 기능 및 작동 흐름

현재 프로젝트는 뉴스 기사 수집, 초기 그룹화, 초기 요약 단계를 중심으로 개발되었습니다. 각 주요 처리 모듈(`src/processing/`) 내의 핵심 NLP 로직(기사 그룹핑, 요약, 편향성 제거)은 아직 실제 모델 연동 없이 임시 플레이스홀더 형태로 구현되어 있으며, 주로 데이터의 흐름과 파일 저장 구조를 검증하는 데 초점을 맞추고 있습니다.

### 1. 뉴스 기사 수집 (`scripts/run_collection.py`)

-   **목적**: 설정 파일에 명시된 뉴스 사이트로부터 기사 데이터를 수집하여 원본(raw) 형태로 저장합니다.
-   **실행**: `python scripts/run_collection.py`
-   **작동 흐름**:
    1.  `configs/news_sites.yaml` 설정 파일을 로드하여 수집 대상 사이트 및 카테고리 정보를 가져옵니다.
    2.  각 사이트 설정에 따라 `src.collection.AVAILABLE_COLLECTORS`에 정의된 적절한 컬렉터 인스턴스(예: `CnnCollector`)를 생성합니다.
        -   `CnnCollector`는 `src.collection.base_collector.BaseCollector`를 상속받아 구현되었습니다.
    3.  선택된 컬렉터의 `collect_by_category` 메소드를 호출하여 각 카테고리별로 기사 링크 목록을 가져오고, 이어 각 링크의 상세 내용을 비동기적으로 수집합니다.
        -   이 과정에서 `aiohttp`를 사용하여 비동기 HTTP 요청을 처리하고, `BeautifulSoup`를 사용하여 HTML 내용을 파싱합니다 (예: `CnnCollector` 내부의 `fetch_article_links`, `fetch_article_content`, `extract_article_details_cnn` 함수).
    4.  수집된 각 기사 데이터는 `src.utils.file_helper.py`의 유틸리티 함수들을 사용하여 JSON 파일로 저장됩니다.
        -   `slugify`: 기사 제목을 파일명으로 사용하기 적합한 형태로 변환합니다.
        -   `get_output_path`: `data/raw/{사이트명}/{카테고리명}/{수집날짜}/` 구조에 맞춰 저장 경로를 생성합니다.
        -   `save_json_async`: 데이터를 비동기적으로 JSON 파일에 씁니다.
    5.  **결과물**: `data/raw/{사이트명}/{카테고리명}/{수집날짜}/{슬러그된_기사제목}.json` 형태로 원본 기사 데이터가 저장됩니다.

### 2. 수집된 기사 그룹핑 (`scripts/run_grouping.py`)

-   **목적**: 수집된 원본 기사들 중 내용이 유사한 것들을 하나의 그룹으로 묶습니다.
-   **실행**: `python scripts/run_grouping.py` (사전에 `run_collection.py` 실행 필요)
-   **작동 흐름**:
    1.  `data/raw/` 디렉토리 하위의 모든 사이트/카테고리/날짜 폴더를 순회하며 저장된 모든 기사 JSON 파일들을 로드합니다 (`src.utils.file_helper.load_json` 사용).
    2.  로드된 전체 기사 리스트를 `src.processing.article_grouper.py`의 `group_articles` 함수에 전달합니다.
        -   **주의**: 현재 `group_articles` 함수는 실제 유사도 비교나 클러스터링 로직 없이, 모든 기사를 하나의 그룹으로 묶는 등 임시적인 로직으로 구현되어 있습니다.
    3.  그룹화된 결과 (기사 그룹 리스트)는 `src.utils.file_helper.py`의 `save_json_async` 함수를 사용하여 JSON 파일로 저장됩니다.
    4.  **결과물**: `data/processed/grouped_articles/{실행날짜}/{그룹ID}.json` 형태로 그룹화된 기사 정보가 저장됩니다.

### 3. 그룹 기사 요약 및 키워드 추출 (`scripts/run_summarization.py`)

-   **목적**: 그룹화된 기사 묶음에 대해 AI 기반 요약문을 생성하고 핵심 키워드를 추출합니다.
-   **실행**: `python scripts/run_summarization.py` (사전에 `run_grouping.py` 실행 필요)
-   **작동 흐름**:
    1.  `data/processed/grouped_articles/` 디렉토리 하위의 날짜 폴더들을 순회하며 저장된 모든 그룹화된 기사 JSON 파일들을 로드합니다 (`load_json` 사용).
    2.  로드된 각 그룹 데이터를 `src.processing.summarizer.py`의 `summarize_and_extract_keywords` 함수에 전달합니다.
        -   **주의**: 현재 `summarize_and_extract_keywords` 함수는 실제 요약 모델이나 키워드 추출 알고리즘 없이, 원본 텍스트의 일부를 가져오는 등 임시적인 로직으로 구현되어 있습니다.
    3.  처리된 결과 (요약문과 키워드가 추가된 그룹 정보)는 `save_json_async` 함수를 사용하여 JSON 파일로 저장됩니다.
    4.  **결과물**: `data/processed/summarized_articles/{실행날짜}/{그룹ID}_summary.json` 형태로 요약 및 키워드 정보가 저장됩니다.

### 향후 구현 예정

-   **편향성 분석 및 제거**: `scripts/run_bias_neutralization.py` 및 `src/processing/bias_neutralizer.py` 구현.
-   **통합 파이프라인**: `src/main.py`를 통해 전체 과정을 통합적으로 관리하고 실행하는 기능.
-   **핵심 NLP 로직 구체화**: `src/processing/` 내의 `group_articles`, `summarize_and_extract_keywords`, `neutralize_bias` 함수에 실제 자연어 처리 모델 및 알고리즘을 적용.
-   **테스트 코드**: `tests/` 디렉토리에 각 모듈 및 전체 흐름에 대한 테스트 코드 작성.

## 폴더 구조 주요 안내

-   `configs/`: 프로젝트 설정 파일 (예: `news_sites.yaml`)
-   `data/`: 모든 데이터 저장
    -   `raw/`: 수집된 원본 기사 (사이트별/카테고리별/날짜별)
    -   `processed/`: 가공된 데이터 (그룹화, 요약, 편향성 제거 결과)
-   `scripts/`: 각 단계별 실행 스크립트
-   `src/`: 핵심 소스 코드
    -   `collection/`: 뉴스 기사 수집 관련 모듈
    -   `processing/`: 기사 그룹핑, 요약, 편향성 제거 등 처리 모듈
    -   `utils/`: 공통 유틸리티 함수 (파일 입출력, 텍스트 처리 등)
-   `requirements.txt`: 프로젝트 의존성 패키지 목록
