# NLLB 파인튜닝 번역 프로젝트

Facebook의 NLLB(No Language Left Behind) 모델을 파인튜닝하여 한국어-영어 번역 성능을 향상시키는 프로젝트입니다.

## 📁 프로젝트 구조

```
├── 01_nllb_import.py          # NLLB 모델 기본 사용법
├── 02_data_preparation.py     # 데이터셋 준비 및 전처리
├── 03_finetune_nllb.py       # 파인튜닝 실행
├── 04_use_finetuned_model.py # 파인튜닝된 모델 사용
├── Dataset/                   # 훈련 데이터 저장 폴더
├── finetuned_nllb/           # 파인튜닝된 모델 저장 폴더
└── README.md                 # 이 파일
```

## 🚀 빠른 시작

### 1단계: 필요한 패키지 설치

```bash
pip install torch transformers datasets tokenizers sentencepiece accelerate evaluate sacrebleu tqdm numpy pandas scikit-learn
```

### 2단계: 기본 NLLB 모델 테스트

```bash
python 01_nllb_import.py
```

### 3단계: 데이터 준비

데이터를 다음 형식으로 준비하세요:

**CSV 형식:**
```csv
source_text,target_text
안녕하세요,Hello
감사합니다,Thank you
```

**JSON 형식:**
```json
[
  {"source": "안녕하세요", "target": "Hello"},
  {"source": "감사합니다", "target": "Thank you"}
]
```

### 4단계: 파인튜닝 실행

```bash
python 03_finetune_nllb.py
```

### 5단계: 파인튜닝된 모델 사용

```bash
python 04_use_finetuned_model.py
```

## 🛠️ 상세 사용법

### 1. 기본 NLLB 모델 사용

```python
from nllb_import import NLLBModel

# 모델 초기화
nllb = NLLBModel("facebook/nllb-200-distilled-600M")

# 번역 실행
result = nllb.translate("안녕하세요", "kor_Hang", "eng_Latn")
print(result)  # Hello
```

### 2. 데이터셋 준비

```python
from data_preparation import load_data_from_csv, create_sample_data

# CSV에서 데이터 로드
source_texts, target_texts = load_data_from_csv("your_data.csv")

# 또는 샘플 데이터 사용
source_texts, target_texts = create_sample_data()
```

### 3. 파인튜닝

```python
from finetune_nllb import NLLBFineTuner

# 파인튜너 초기화
fine_tuner = NLLBFineTuner()

# 훈련 실행
fine_tuner.train(
    source_texts=source_texts,
    target_texts=target_texts,
    epochs=10,
    learning_rate=5e-5,
    batch_size=4
)
```

### 4. 파인튜닝된 모델 사용

```python
from use_finetuned_model import FineTunedNLLBTranslator

# 번역기 초기화
translator = FineTunedNLLBTranslator("./finetuned_nllb")

# 번역 실행
result = translator.translate("안녕하세요")
print(result)
```

## 🎯 지원하는 언어

| 언어 | 코드 |
|------|------|
| 한국어 | kor_Hang |
| 영어 | eng_Latn |
| 일본어 | jpn_Jpan |
| 중국어(간체) | zho_Hans |
| 중국어(번체) | zho_Hant |
| 스페인어 | spa_Latn |
| 프랑스어 | fra_Latn |
| 독일어 | deu_Latn |
| 러시아어 | rus_Cyrl |
| 아랍어 | arb_Arab |

## ⚙️ 파인튜닝 파라미터 조정

### GPU 메모리에 따른 배치 크기 조정

- **4GB GPU**: batch_size=1
- **8GB GPU**: batch_size=2-4
- **16GB GPU**: batch_size=4-8
- **24GB+ GPU**: batch_size=8+

### 학습률 조정

- **기본값**: 5e-5
- **더 보수적**: 1e-5
- **더 공격적**: 1e-4

### 에포크 수

- **소규모 데이터**: 10-20 에포크
- **대규모 데이터**: 3-5 에포크

## 📊 성능 모니터링

훈련 중 다음 지표들을 모니터링하세요:

- **훈련 손실 (Training Loss)**: 감소해야 함
- **검증 손실 (Validation Loss)**: 감소 후 안정화
- **과적합 감지**: 검증 손실이 증가하기 시작하면 조기 종료

## 🔧 문제 해결

### 1. CUDA 메모리 부족

```python
# 배치 크기 줄이기
batch_size = 1

# 그래디언트 누적 사용
accumulation_steps = 4
```

### 2. 훈련이 느린 경우

```python
# 더 작은 모델 사용
model_name = "facebook/nllb-200-distilled-600M"  # 대신 600M 모델 사용

# 혼합 정밀도 훈련
from torch.cuda.amp import autocast, GradScaler
```

### 3. 번역 품질이 낮은 경우

- 더 많은 훈련 데이터 수집
- 에포크 수 증가
- 학습률 조정
- 데이터 품질 검토

## 📝 주의사항

1. **데이터 품질**: 고품질의 병렬 데이터가 필수
2. **GPU 메모리**: 최소 4GB GPU 권장
3. **훈련 시간**: 데이터 크기에 따라 몇 시간에서 며칠 소요
4. **모델 크기**: 파인튜닝된 모델은 1-3GB 크기

## 🤝 기여 방법

1. 이슈 등록
2. 포크 후 브랜치 생성
3. 변경사항 커밋
4. 풀 리퀘스트 생성

## �� 라이선스

MIT License
