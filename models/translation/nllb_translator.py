import torch
import os
import sys
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import logging
import re

class NLLBTranslator:
    """
    NHNDQ/nllb-finetuned-en2ko 모델을 사용한 번역기
    영어 → 한국어 번역 전용
    """
    
    def __init__(self, model_name="NHNDQ/nllb-finetuned-en2ko", device=None):
        """
        번역기 초기화
        
        Args:
            model_name: 사용할 모델명 (기본값: NHNDQ/nllb-finetuned-en2ko)
            device: 사용할 디바이스 (None이면 자동 감지)
        """
        self.model_name = model_name
        self.src_lang = "eng_Latn"  # 영어
        self.tgt_lang = "kor_Hang"  # 한국어
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        logging.info(f"번역기 초기화 - 모델: {model_name}")
        logging.info(f"디바이스: {self.device}")
        logging.info(f"번역 방향: 영어 → 한국어")
        
        # 모델 로드
        self._load_model()
        
    def _load_model(self):
        """
        사전 훈련된 모델과 토크나이저 로드
        """
        try:
            logging.info(f"모델 다운로드 및 로드 중: {self.model_name}")
            
            # Hugging Face에서 모델 로드
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            
            self.model.to(self.device)
            self.model.eval()
            
            logging.info("모델 로드 완료!")
            logging.info(f"모델 파라미터 수: {sum(p.numel() for p in self.model.parameters()):,}")
            
        except Exception as e:
            logging.error(f"모델 로드 실패: {e}")
            logging.info("기본 NLLB 모델로 fallback 시도...")
            
            try:
                # Fallback to base NLLB model
                fallback_model = "facebook/nllb-200-distilled-600M"
                self.tokenizer = AutoTokenizer.from_pretrained(fallback_model)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(fallback_model)
                self.model.to(self.device)
                self.model.eval()
                logging.info(f"Fallback 모델 로드 완료: {fallback_model}")
            except Exception as fallback_error:
                logging.error(f"Fallback 모델 로드도 실패: {fallback_error}")
                raise
    
    def translate(self, english_text, max_length_per_chunk=400, num_beams=5):
        """
        영어 텍스트를 한국어로 번역. 긴 텍스트는 자동으로 분할하여 처리.
        
        Args:
            english_text: 번역할 영어 텍스트
            max_length_per_chunk: 한 번에 처리할 최대 토큰 길이
            num_beams: 빔 서치 크기
            
        Returns:
            번역된 한국어 텍스트
        """
        if not english_text or not isinstance(english_text, str) or not english_text.strip():
            return ""

        # 텍스트를 문장 단위로 분할 (정규식 사용, nltk 불필요)
        sentences = re.split(r'(?<=[.!?])\s+', english_text.strip())
        
        chunks = []
        current_chunk = ""

        # 문장을 청크로 그룹화
        for sentence in sentences:
            if len(self.tokenizer.tokenize(current_chunk + " " + sentence)) > max_length_per_chunk:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)

        translated_chunks = []
        try:
            self.tokenizer.src_lang = self.src_lang
            
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue

                # 텍스트 토큰화
                inputs = self.tokenizer(
                    chunk, 
                    return_tensors="pt",
                    truncation=True, # 청크가 혹시 길 경우를 대비한 최종 방어선
                    padding=True
                ).to(self.device)
                
                # 번역 생성
                with torch.no_grad():
                    generated_tokens = self.model.generate(
                        **inputs,
                        forced_bos_token_id=self.tokenizer.lang_code_to_id[self.tgt_lang],
                        max_new_tokens=int(len(chunk) * 1.5), # 번역 결과가 원문보다 길어질 경우를 대비
                        num_beams=num_beams,
                        early_stopping=True,
                        do_sample=False,
                    )
                
                # 결과 디코딩
                translated_chunk = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
                translated_chunks.append(translated_chunk.strip())
                logging.info(f"청크 {i+1}/{len(chunks)} 번역 완료.")
            
            return " ".join(translated_chunks)
            
        except Exception as e:
            logging.error(f"번역 실패 - 입력: '{english_text[:50]}...', 오류: {e}")
            return f"[Translation Error: {str(e)}]"
    
    def batch_translate(self, english_texts, batch_size=4):
        """
        여러 영어 텍스트를 배치로 번역
        
        Args:
            english_texts: 번역할 영어 텍스트 리스트
            batch_size: 배치 크기
            
        Returns:
            번역된 한국어 텍스트 리스트
        """
        results = []
        
        for i in range(0, len(english_texts), batch_size):
            batch_texts = english_texts[i:i + batch_size]
            batch_results = []
            
            for text in batch_texts:
                result = self.translate(text)
                batch_results.append(result)
            
            results.extend(batch_results)
            logging.info(f"배치 번역 진행: {min(i + batch_size, len(english_texts))}/{len(english_texts)}")
            
        return results
    
    def is_english_text(self, text):
        """
        텍스트가 영어인지 확인 (langdetect 사용)
        
        Args:
            text: 확인할 텍스트
            
        Returns:
            영어 여부 (bool)
        """
        if not text or len(text.strip()) < 10:
            return False
            
        try:
            from langdetect import detect
            detected_lang = detect(text)
            return detected_lang == 'en'
        except:
            # langdetect 실패 시 간단한 영어 문자 비율로 판단
            english_chars = sum(1 for char in text if char.isascii() and char.isalpha())
            total_chars = len([char for char in text if char.isalpha()])
            
            if total_chars == 0:
                return False
                
            # 영어 비율이 80% 이상이면 영어로 판단
            english_ratio = english_chars / total_chars
            return english_ratio >= 0.8
    
    def get_model_info(self):
        """
        모델 정보 반환
        """
        return {
            "model_name": self.model_name,
            "source_language": "English (eng_Latn)",
            "target_language": "Korean (kor_Hang)", 
            "device": str(self.device),
            "parameters": sum(p.numel() for p in self.model.parameters()) if hasattr(self, 'model') else 0
        } 