import google.generativeai as genai
import os
import time
from typing import Optional

class GeminiAPIRefiner:
    """
    Gemini API를 사용하여 기사를 요약하고 다듬는 클래스.
    """
    def __init__(self):
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self.request_timestamps = []
        self.rate_limit_per_minute = 15

    def _apply_rate_limit(self, delay=5):
        """API 요청 빈도를 제어합니다."""
        now = time.monotonic()
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60]
        if len(self.request_timestamps) >= self.rate_limit_per_minute:
            time.sleep(delay)
        self.request_timestamps.append(time.monotonic())

    def refine_text(self, title: str, body: str) -> Optional[str]:
        """Gemini API를 사용하여 제목과 본문을 받아 세련된 기사로 재작성합니다."""
        if not body or not body.strip():
            print("  - 요약할 내용이 없어 스킵합니다.")
            return None

        if not title:
            title = "제목 없음"

        prompt = f"""당신은 주어진 '원본 본문'을 바탕으로, 사실에 입각한 중립적인 뉴스 기사 본문을 작성하는 전문 편집자입니다. 아래 가이드라인을 엄격히 준수하여 결과물을 생성해야 합니다.

**[가이드라인]**
- **출력 형식:** 최종 결과물은 **오직 기사 본문**이어야 합니다. 제목, 부제, 서문, 설명 등 그 어떤 추가적인 텍스트도 포함해서는 안 됩니다.
- **구조:** 3~5개의 문단으로 구성된 본문. 문단과 문단 사이는 반드시 2번의 줄 바꿈(\n\n)으로 구분해야 합니다.
- **분량:** 전체 본문은 공백 포함 500자 ~ 700자 사이로 작성합니다.
- **내용:** '원본 본문'의 핵심 사실만을 사용해 객관적으로 재구성합니다. '참고용 원본 제목'은 문맥 파악에만 활용하고, 내용에 포함시키지 마십시오. 주관적 해석, 감정적 표현, 추측성 문장을 철저히 배제하고 중립성을 유지해야 합니다.
- **교정:** 원본의 오탈자, 문법 오류, 불필요한 표현은 모두 수정합니다.

**[참고용 원본 제목]**
{title}

**[재작성할 원본 본문]**
{body}

**[완성된 기사 본문]**
"""
        try:
            self._apply_rate_limit()
            response = self.model.generate_content(prompt)
            if response.candidates:
                refined_text = response.text.strip()
                return refined_text
            else:
                print("  - Gemini API에서 유효한 응답을 받지 못했습니다.")
                return None
        except Exception as e:
            print(f"  - Gemini API 호출 중 에러 발생: {e}")
            return None

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

class KoBARTSummarizer:
    """
    KoBART 모델을 사용하여 텍스트를 요약하는 클래스.
    """
    def __init__(self, model_path: str):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"KoBART Summarizer를 '{self.device}'에서 로드합니다.")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(self.device)
        except Exception as e:
            print(f"모델 로딩 중 에러 발생: {e}")
            raise

    def summarize(self, text: str, max_length: int = 1024, min_length: int = 64) -> Optional[str]:
        """
        주어진 텍스트를 요약합니다.
        """
        if not text or not text.strip():
            print("  - 요약할 내용이 없어 스킵합니다.")
            return None

        try:
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=max_length
            ).to(self.device)
            
            summary_ids = self.model.generate(
                inputs['input_ids'],
                num_beams=4,
                max_length=max_length,
                min_length=min_length,
                length_penalty=1.2,
                repetition_penalty=1.5,
                early_stopping=True
            )
            
            summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            return summary.strip()
        
        except Exception as e:
            print(f"  - KoBART 요약 중 에러 발생: {e}")
            return None