from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM,
    M2M100ForConditionalGeneration,
    NllbTokenizer
)
import torch

# NLLB 모델 종류
# - facebook/nllb-200-distilled-600M (가벼운 버전)
# - facebook/nllb-200-1.3B (중간 크기)
# - facebook/nllb-200-3.3B (큰 버전)

class NLLBModel:
    def __init__(self, model_name="facebook/nllb-200-distilled-600M"):
        """
        NLLB 모델 초기화
        """
        self.model_name = model_name
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"사용 중인 디바이스: {self.device}")
        
        # 모델과 토크나이저 로드
        print(f"모델 로딩 중: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.to(self.device)
        
        print("모델 로딩 완료!")
    
    def translate(self, text, src_lang="kor_Hang", tgt_lang="eng_Latn"):
        """
        기본 번역 함수
        """
        # 토크나이저에 소스 언어 설정
        self.tokenizer.src_lang = src_lang
        
        # 텍스트 토큰화
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        
        # 번역 생성
        with torch.no_grad():
            generated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.lang_code_to_id[tgt_lang],
                max_length=512,
                num_beams=5,
                early_stopping=True
            )
        
        # 결과 디코딩
        result = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        return result

# 테스트 코드
if __name__ == "__main__":
    # 모델 초기화
    nllb = NLLBModel()
    
    # 테스트 번역
    korean_text = "안녕하세요, 오늘 날씨가 좋네요."
    english_result = nllb.translate(korean_text, "kor_Hang", "eng_Latn")
    
    print(f"한국어: {korean_text}")
    print(f"영어: {english_result}") 