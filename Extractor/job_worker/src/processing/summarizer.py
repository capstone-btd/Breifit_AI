from typing import List, Dict, Tuple
import os
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import re

def summarize_and_extract_keywords(grouped_articles_data: List[Dict]) -> List[Dict]:
    """
    그룹화된 기사 묶음 또는 개별 기사 내용을 받아 요약하고 핵심 키워드를 추출합니다.

    Args:
        grouped_articles_data (List[Dict]): group_articles의 결과물.
                                           각 딕셔너리는 "group_id", "articles" 리스트 등을 포함.
                                           또는 요약할 단일 기사 텍스트를 가진 객체 리스트일 수도 있음.

    Returns:
        List[Dict]: 각 그룹/기사에 대한 요약 및 키워드 정보가 추가된 리스트.
                    예: [
                        {
                            "group_id": "unique_group_id_1", (또는 "article_id")
                            "original_data": { ... }, (선택적: 원본 그룹/기사 정보)
                            "summary": "AI가 생성한 요약문...",
                            "extracted_keywords": ["중요키워드A", "중요키워드B"]
                        },
                        ...
                    ]
    """
    print("문서 요약 및 키워드 추출 로직 실행...")
    processed_data = []

    for group_data in grouped_articles_data:
        group_id = group_data.get("group_id", "unknown_group")
        
        # 그룹 내 모든 기사 텍스트를 합치거나, 대표 기사 텍스트를 선택
        # 여기서는 간단히 첫 번째 기사의 텍스트를 사용한다고 가정
        # 실제로는 모든 텍스트를 취합하거나, 가장 중요한 기사를 선별하는 로직 필요
        text_to_summarize = ""
        if group_data.get("articles") and isinstance(group_data["articles"], list) and len(group_data["articles"]) > 0:
            # 그룹의 경우 여러 기사 텍스트를 취합하는 로직 필요
            # 여기서는 첫번째 기사의 텍스트를 임시로 사용
            first_article_in_group = group_data["articles"][0]
            text_to_summarize = first_article_in_group.get("article_text", "")
            if not text_to_summarize: # article_text가 없을 경우 title이라도.
                 text_to_summarize = first_article_in_group.get("title", "")
        elif group_data.get("article_text"): # 단일 기사 객체의 경우
            text_to_summarize = group_data["article_text"]
        
        if not text_to_summarize:
            print(f"경고: {group_id}에 대해 요약할 텍스트가 없습니다.")
            summary = "요약할 내용 없음."
            keywords = []
        else:
            # === 구현 예정: 실제 요약 및 키워드 추출 모델 연동 ===
            # 예: Hugging Face Transformers 라이브러리의 요약 모델 (BART, T5 등)
            # 예: KoBART (한국어 요약), KeyBERT 또는 TF-IDF 기반 키워드 추출
            summary = f"요약된 내용: {text_to_summarize[:100]}..." # 임시 요약
            keywords = [word for word in text_to_summarize.split()[:5] if len(word) > 3] # 임시 키워드

        processed_data.append({
            "group_id": group_id,
            "summary": summary,
            "extracted_keywords": keywords,
            "original_group_data": group_data # 원본 그룹 정보 포함 (선택적)
        })
        print(f"{group_id}에 대한 요약 및 키워드 추출 완료.")
        
    return processed_data 

class Summarizer:
    def __init__(self, model_path: str = "models/summarization", device: str = None):
        """
        기능: 요약 모델과 토크나이저를 메모리에 로드하고 초기화합니다.
        input: model_path (모델 파일들이 저장된 경로), device (모델을 실행할 장치, e.g., 'cuda' or 'cpu')
        output: 없음
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"모델 경로를 찾을 수 없습니다: {model_path}")

        print(f"'{model_path}'에서 요약 모델을 로딩합니다...")
        
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        print(f"Summarizer가 사용할 장치: {self.device.upper()}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(self.device)
        self.max_input_length = 1024
        
        weird_endings = list(set([
            '했다', '강조했다', '습니다', '했습니다', '덧붙였다', '한다', 
            '설명했다', '분석했다', '전해졌다', '상황이다', '전망이다', 
            '됩니다', '나타났다', '있습니다', '된다', '겁니다', '됐다', 
            '적이다', '계획이다', '해왔다', '하다', '증가했다', '것이다', 
            '예정이다', '방침이다', '풀이된다', '밝혔다', '말했다', '전했다'
        ]))
        self.ending_pattern = re.compile(r"(\s*(" + "|".join(re.escape(e) for e in weird_endings) + r")\.)+\s*$")
        
        print("요약 모델 로딩 완료.")

    def _clean_summary_endings(self, summary: str) -> str:
        """
        기능: 요약문 끝에 반복적으로 나타나는 부자연스러운 동사 어미를 제거합니다.
        input: summary (원본 요약문)
        output: 어미가 제거된 요약문
        """
        return self.ending_pattern.sub("", summary).strip()

    def _summarize_internal(self, text: str, max_length: int, num_beams: int, length_penalty: float) -> str:
        """
        기능: 입력된 텍스트에 대해 실제 요약 연산을 수행하는 내부 함수입니다.
        input: text (요약할 텍스트), max_length (최대 생성 길이), num_beams (빔 서치 너비), length_penalty (길이 페널티)
        output: 요약된 텍스트 문자열
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_input_length
        ).to(self.device)

        summary_ids = self.model.generate(
            **inputs,
            max_length=max_length,
            num_beams=num_beams,
            length_penalty=length_penalty,
            no_repeat_ngram_size=2,
            early_stopping=True
        )
        summary_text = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()
        cleaned_summary = self._clean_summary_endings(summary_text)
        return cleaned_summary

    def summarize(self, text: str, max_length: int = 256, num_beams: int = 5, length_penalty: float = 1.2) -> str:
        """
        기능: 주어진 텍스트를 요약합니다. 텍스트가 모델의 최대 입력 길이를 초과할 경우, '요약의 요약' 방식을 사용하여 정보 손실 없이 처리합니다.
        input: text (요약할 원본 텍스트), max_length (최종 요약문 최대 길이), num_beams (빔 서치 너비), length_penalty (길이 페널티)
        output: 생성된 최종 요약문
        """
        if not text:
            return ""

        input_token_ids = self.tokenizer(text, truncation=False, return_tensors="pt")["input_ids"][0]
        
        if len(input_token_ids) <= self.max_input_length:
            return self._summarize_internal(text, max_length, num_beams, length_penalty)

        print(f"  - 입력 텍스트가 너무 길어({len(input_token_ids)} 토큰) '요약의 요약' 방식을 사용합니다.")
        
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk_tokens = []

        for p in paragraphs:
            paragraph_tokens = self.tokenizer(p, truncation=False)["input_ids"]
            
            if len(current_chunk_tokens) + len(paragraph_tokens) <= self.max_input_length:
                current_chunk_tokens.extend(paragraph_tokens)
            else:
                if current_chunk_tokens:
                    chunks.append(self.tokenizer.decode(current_chunk_tokens, skip_special_tokens=True))
                current_chunk_tokens = paragraph_tokens
        
        if current_chunk_tokens:
            chunks.append(self.tokenizer.decode(current_chunk_tokens, skip_special_tokens=True))

        partial_summaries = []
        for i, chunk in enumerate(chunks):
            print(f"    - 청크 {i+1}/{len(chunks)} 요약 중...")
            partial_summary = self._summarize_internal(chunk, max_length=512, num_beams=num_beams, length_penalty=length_penalty)
            partial_summaries.append(partial_summary)
            
        stitched_summary = "\n".join(partial_summaries)
        print(f"    - 부분 요약들을 합쳐 최종 요약 생성 중...")
        final_summary = self._summarize_internal(stitched_summary, max_length=max_length, num_beams=num_beams, length_penalty=length_penalty)

        return final_summary

    def summarize_batch(self, texts: List[str], batch_size: int = 4, **kwargs) -> List[str]:
        """
        기능: 여러 텍스트를 배치 단위로 요약합니다. (주의: 이 함수는 긴 텍스트를 자동으로 잘라냅니다.)
        input: texts (요약할 텍스트 리스트), batch_size (한 번에 처리할 배치 크기), kwargs (summarize 함수에 전달될 추가 인자)
        output: 요약된 텍스트 리스트
        """
        summaries = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=1024
            ).to(self.device)

            summary_ids = self.model.generate(
                inputs['input_ids'],
                attention_mask=inputs['attention_mask'],
                **kwargs
            )
            
            batch_summaries = self.tokenizer.batch_decode(summary_ids, skip_special_tokens=True)
            summaries.extend([s.strip() for s in batch_summaries])
        
        return summaries 