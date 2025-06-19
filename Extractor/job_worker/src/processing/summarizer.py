from typing import List, Dict, Tuple
import os
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import re
from collections import Counter
from konlpy.tag import Okt
import kss

def clean_summary(summary_text: str) -> str:
    # 모델이 생성하는 경향이 있는 후행 아티팩트 단어 목록
    artifact_words = [
        '강조했다', '습니다', '전해졌다', '한다', '설명했다', '받는다', '상황이다',
        '예정이다', '상태다', '것이다', '덧붙였다', '방침이다', '분석했다', '밝혔다',
        '평가했다', '수준이다', '했습니다', '겁니다', '진단했다', '됐다', '했다',
        '였다', '이다', '이었다', '이라고', '으로', '등', '등이', '이런', '것', '뿐',
        '입니다', '됐습니다', '했습니다', '졌습니다', '위해'
    ]
    
    # 후행 아티팩트를 제거하기 위한 정규식. `( (?:단어1|단어2...)\s*\.?\s*)+$` 형태.
    pattern = r'(\s*(?:' + '|'.join(artifact_words) + r')\s*\.?\s*)+$'
    cleaned_text = re.sub(pattern, '', summary_text.strip())

    # 불필요한 등호나 특수 문자 제거
    cleaned_text = re.sub(r'={4,}\s*[^가-힣a-zA-Z0-9\s]*', '', cleaned_text)
    
    # 문장 끝의 공백 및 중복 마침표 정리
    cleaned_text = re.sub(r'\s*([.?!])\s*$', r'\1', cleaned_text.strip())
    cleaned_text = re.sub(r'(\s*[.!?])+', r'\1', cleaned_text)
    
    # 자음/모음만 있는 경우 제거
    cleaned_text = re.sub(r'[ㄱ-ㅎㅏ-ㅣ]+', '', cleaned_text)

    # 한 단어로만 이루어진 문장 제거 로직 추가
    if cleaned_text.strip():
        sentences = [s.strip() for s in cleaned_text.split('.') if s.strip()]
        # 단어 개수가 1개 이하인 문장 필터링
        filtered_sentences = [s for s in sentences if len(s.split()) > 1]
        
        if not filtered_sentences:
             # 모든 문장이 필터링되면 원본 텍스트의 첫 문장이라도 반환 (안전장치)
            return sentences[0] if sentences else ""
            
        cleaned_text = ". ".join(filtered_sentences)
        # 마지막 문장에 마침표 추가
        if not cleaned_text.endswith('.'):
            cleaned_text += '.'
            
    return cleaned_text.strip()


class KeywordExtractor:
    def __init__(self):
        self.okt = Okt()

    def extract_keywords(self, text: str, num_keywords: int = 5) -> List[str]:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return []

        nouns = self.okt.nouns(text)
        
        filtered_nouns = [
            word for word in nouns 
            if len(word) > 1 and not word.isdigit() and word not in ["대한", "이번", "지난", "등", "때문", "관련", "오늘", "내일", "오후", "오전"]
        ]
        
        if not filtered_nouns:
            return []
            
        keyword_counts = Counter(filtered_nouns)
        top_keywords = [word for word, count in keyword_counts.most_common(num_keywords)]
        
        return top_keywords


class Summarizer:
    def __init__(self, model_path: str, device: str = 'auto'):
        print(f"'{model_path}'에서 요약 모델을 로딩합니다...")
        
        if device == 'auto':
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        else:
            self.device = device
        
        print(f"Summarizer가 사용할 장치: {self.device.upper()}")

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(self.device)
            
            model_max_len = self.tokenizer.model_max_length
            self.max_input_length = min(model_max_len, 1024) if model_max_len < 1e10 else 1024
            
        except OSError as e:
            print(f"오류: '{model_path}'에서 모델/토크나이저 로딩에 실패했습니다. 경로를 확인해주세요.")
            raise e

    def _chunk_text(self, text: str, max_length: int) -> list[str]:
        sentences = kss.split_sentences(text)
        
        chunks = []
        current_chunk_sentences = []
        current_chunk_length = 0

        for sentence in sentences:
            sentence_tokens = self.tokenizer.encode(sentence, add_special_tokens=False)
            sentence_length = len(sentence_tokens)

            if sentence_length > max_length:
                if current_chunk_sentences:
                    chunks.append(" ".join(current_chunk_sentences))
                    current_chunk_sentences = []
                    current_chunk_length = 0
                
                # 문장 자체가 너무 길면, 해당 문장을 토큰 기반으로 분할
                sub_chunks = []
                for i in range(0, sentence_length, max_length):
                    chunk_tokens = sentence_tokens[i:i + max_length]
                    sub_chunks.append(self.tokenizer.decode(chunk_tokens, skip_special_tokens=True))
                chunks.extend(sub_chunks)
                continue

            if current_chunk_length + sentence_length <= max_length:
                current_chunk_sentences.append(sentence)
                current_chunk_length += sentence_length
            else:
                chunks.append(" ".join(current_chunk_sentences))
                current_chunk_sentences = [sentence]
                current_chunk_length = sentence_length
        
        if current_chunk_sentences:
            chunks.append(" ".join(current_chunk_sentences))
            
        return chunks


    def summarize(self, text: str) -> str:
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            print("  - 요약할 내용이 없어 건너뜁니다.")
            return ""

        chunks = self._chunk_text(text, max_length=self.max_input_length - 10) 

        summaries = [self._generate(c, max_len=256) for c in chunks]
        
        final_summary = " ".join(summaries)

        final_summary = clean_summary(final_summary)
        
        return final_summary

    def _generate(self, text: str, max_len: int) -> str:
        inputs = self.tokenizer(
            text, 
            return_tensors="pt",
            max_length=self.max_input_length,
            truncation=True
        ).to(self.device)

        summary_ids = self.model.generate(
            inputs['input_ids'],
            num_beams=5,
            length_penalty=1.5,
            max_length=max_len,
            min_length=max(20, max_len // 5),
            no_repeat_ngram_size=3,
            early_stopping=True,
            repetition_penalty=1.2,
        )
        
        summary = self.tokenizer.decode(summary_ids.squeeze(), skip_special_tokens=True)
        return summary

    def summarize_batch(self, texts: List[str], batch_size: int = 4, **kwargs) -> List[str]:
        summaries = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            inputs = self.tokenizer(
                batch,
                return_tensors="pt",
                truncation=True,
                padding=True,
                max_length=self.max_input_length
            ).to(self.device)

            summary_ids = self.model.generate(
                inputs['input_ids'],
                attention_mask=inputs['attention_mask'],
                num_beams=5,
                length_penalty=1.5,
                max_length=1024,
                min_length=max(20, 1024 // 5),
                no_repeat_ngram_size=3,
                early_stopping=True,
                repetition_penalty=1.2,
                **kwargs
            )
            
            batch_summaries = self.tokenizer.batch_decode(summary_ids, skip_special_tokens=True)
            cleaned_batch_summaries = [clean_summary(s.strip()) for s in batch_summaries]
            summaries.extend(cleaned_batch_summaries)
        
        return summaries


def summarize_and_extract_keywords(
    grouped_articles_data: List[Dict], 
    summarizer_model_path: str,
    device: str = 'auto'
) -> List[Dict]:
    print("문서 요약 및 키워드 추출 로직 실행...")
    processed_data = []

    try:
        summarizer = Summarizer(model_path=summarizer_model_path, device=device)
    except OSError:
        print("요약 모델 로딩에 실패했습니다. 요약 기능을 건너뛰고 기본값으로 처리합니다.")
        summarizer = None

    keyword_extractor = KeywordExtractor()

    for group_data in grouped_articles_data:
        group_id = group_data.get("group_id", "unknown_group")
        
        # 1. 기사 '내용(article_text)'만 수집
        article_contents = []
        if group_data.get("articles") and isinstance(group_data["articles"], list):
            for article in group_data["articles"]:
                if article.get("article_text"):
                    article_contents.append(article["article_text"])
        elif group_data.get("article_text"): # 단일 기사 케이스
            article_contents.append(group_data["article_text"])
            
        text_to_summarize = " ".join(article_contents)
        
        summary = ""
        keywords = []

        # 2. 요약할 내용이 있는지 확인
        if text_to_summarize.strip():
            # 내용이 있으면 요약 수행
            if summarizer:
                summary = summarizer.summarize(text_to_summarize)
                if not summary.strip():
                    summary = f"[요약 실패/짧음] {text_to_summarize[:150].strip()}..."
            else:
                summary = f"[모델 로딩 실패] {text_to_summarize[:150].strip()}..."
            
            keywords = keyword_extractor.extract_keywords(text_to_summarize)
        else:
            # 내용이 없으면 대표 제목을 결과로 사용
            print(f"경고: {group_id}에 대해 요약할 텍스트가 없습니다. 대표 제목을 결과로 사용합니다.")
            representative_title = ""
            if group_data.get("articles") and isinstance(group_data["articles"], list) and len(group_data["articles"]) > 0:
                if group_data["articles"][0].get("title"):
                    representative_title = group_data["articles"][0]["title"]
            elif group_data.get("title"):
                representative_title = group_data.get("title")

            summary = representative_title
            # 내용이 없을 경우, 제목에서라도 키워드를 추출 시도
            if representative_title:
                keywords = keyword_extractor.extract_keywords(representative_title)

        processed_data.append({
            "group_id": group_id,
            "summary": summary,
            "extracted_keywords": keywords,
            "original_group_data": group_data
        })
        print(f"'{group_id}'에 대한 요약 및 키워드 추출 완료.")
        
    return processed_data

