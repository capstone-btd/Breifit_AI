import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import json
import os

class FineTunedNLLBTranslator:
    def __init__(self, model_path="./finetuned_nllb", 
                 src_lang="kor_Hang", tgt_lang="eng_Latn"):
        """
        파인튜닝된 NLLB 번역기
        
        Args:
            model_path: 파인튜닝된 모델이 저장된 경로
            src_lang: 소스 언어 코드
            tgt_lang: 타겟 언어 코드
        """
        self.model_path = model_path
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"사용 디바이스: {self.device}")
        print(f"모델 로딩: {model_path}")
        
        # 파인튜닝된 모델과 토크나이저 로드
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
            self.model.to(self.device)
            self.model.eval()  # 추론 모드로 설정
            print("파인튜닝된 모델 로딩 완료!")
            
            # 훈련 로그 확인
            self.load_training_log()
            
        except Exception as e:
            print(f"모델 로딩 오류: {e}")
            print("기본 NLLB 모델을 사용합니다.")
            self.tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
            self.model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-distilled-600M")
            self.model.to(self.device)
            self.model.eval()
    
    def load_training_log(self):
        """
        훈련 로그 로드
        """
        log_path = os.path.join(self.model_path, "training_log.json")
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                self.training_log = json.load(f)
                print(f"훈련 에포크: {self.training_log['epochs']}")
                print(f"최종 훈련 손실: {self.training_log['train_losses'][-1]:.4f}")
                print(f"최종 검증 손실: {self.training_log['val_losses'][-1]:.4f}")
        else:
            self.training_log = None
            print("훈련 로그를 찾을 수 없습니다.")
    
    def translate(self, text, max_length=512, num_beams=5, 
                  temperature=1.0, do_sample=False):
        """
        텍스트 번역
        
        Args:
            text: 번역할 텍스트
            max_length: 최대 생성 길이
            num_beams: 빔 서치 크기
            temperature: 샘플링 온도 (do_sample=True일 때)
            do_sample: 샘플링 사용 여부
        """
        # 소스 언어 설정
        self.tokenizer.src_lang = self.src_lang
        
        # 텍스트 토큰화
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        
        # 번역 생성
        with torch.no_grad():
            generate_kwargs = {
                "input_ids": inputs["input_ids"],
                "attention_mask": inputs["attention_mask"],
                "forced_bos_token_id": self.tokenizer.lang_code_to_id[self.tgt_lang],
                "max_length": max_length,
                "early_stopping": True
            }
            
            if do_sample:
                generate_kwargs.update({
                    "do_sample": True,
                    "temperature": temperature,
                    "top_p": 0.9
                })
            else:
                generate_kwargs.update({
                    "num_beams": num_beams
                })
            
            generated_tokens = self.model.generate(**generate_kwargs)
        
        # 결과 디코딩
        result = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        return result
    
    def batch_translate(self, texts, batch_size=4):
        """
        배치 번역
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_results = []
            
            for text in batch_texts:
                result = self.translate(text)
                batch_results.append(result)
            
            results.extend(batch_results)
            print(f"번역 진행: {min(i + batch_size, len(texts))}/{len(texts)}")
        
        return results
    
    def interactive_translate(self):
        """
        대화형 번역 모드
        """
        print("\n=== 대화형 번역 모드 ===")
        print("번역할 텍스트를 입력하세요. (종료: 'quit' 또는 'exit')")
        print(f"언어 방향: {self.src_lang} → {self.tgt_lang}")
        print("-" * 50)
        
        while True:
            try:
                text = input("\n입력: ").strip()
                
                if text.lower() in ['quit', 'exit', '종료']:
                    print("번역을 종료합니다.")
                    break
                
                if not text:
                    continue
                
                # 번역 수행
                result = self.translate(text)
                print(f"번역: {result}")
                
            except KeyboardInterrupt:
                print("\n번역을 종료합니다.")
                break
            except Exception as e:
                print(f"번역 오류: {e}")
    
    def evaluate_samples(self, test_pairs):
        """
        테스트 샘플들에 대한 번역 평가
        
        Args:
            test_pairs: [(source, expected_target), ...] 형태의 리스트
        """
        print("\n=== 번역 평가 ===")
        
        for i, (source, expected) in enumerate(test_pairs):
            predicted = self.translate(source)
            
            print(f"\n샘플 {i + 1}:")
            print(f"입력: {source}")
            print(f"예상: {expected}")
            print(f"번역: {predicted}")
            print("-" * 30)
    
    def save_translations(self, texts, output_file="translations.json"):
        """
        번역 결과를 파일로 저장
        """
        translations = []
        
        for text in texts:
            result = self.translate(text)
            translations.append({
                "source": text,
                "translation": result,
                "src_lang": self.src_lang,
                "tgt_lang": self.tgt_lang
            })
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(translations, f, ensure_ascii=False, indent=2)
        
        print(f"번역 결과가 {output_file}에 저장되었습니다.")

# 언어 코드 참조
LANGUAGE_CODES = {
    "한국어": "kor_Hang",
    "영어": "eng_Latn", 
    "일본어": "jpn_Jpan",
    "중국어(간체)": "zho_Hans",
    "중국어(번체)": "zho_Hant",
    "스페인어": "spa_Latn",
    "프랑스어": "fra_Latn",
    "독일어": "deu_Latn",
    "러시아어": "rus_Cyrl",
    "아랍어": "arb_Arab"
}

def print_language_codes():
    """
    지원하는 언어 코드 출력
    """
    print("\n=== 지원하는 언어 코드 ===")
    for lang, code in LANGUAGE_CODES.items():
        print(f"{lang}: {code}")

# 메인 실행 코드
if __name__ == "__main__":
    # 언어 코드 참조 출력
    print_language_codes()
    
    # 번역기 초기화 (한국어 → 영어)
    translator = FineTunedNLLBTranslator(
        model_path="./finetuned_nllb",
        src_lang="kor_Hang",
        tgt_lang="eng_Latn"
    )
    
    # 테스트 샘플들
    test_samples = [
        "안녕하세요, 만나서 반갑습니다.",
        "오늘 날씨가 정말 좋네요.",
        "이 프로젝트는 정말 흥미롭습니다.",
        "도움이 필요하시면 언제든지 연락하세요.",
        "감사합니다. 좋은 하루 되세요!"
    ]
    
    print("\n=== 번역 테스트 ===")
    for i, text in enumerate(test_samples):
        result = translator.translate(text)
        print(f"{i+1}. {text}")
        print(f"   → {result}")
        print()
    
    # 대화형 번역 모드 (선택사항)
    use_interactive = input("대화형 번역 모드를 사용하시겠습니까? (y/n): ").lower()
    if use_interactive == 'y':
        translator.interactive_translate() 