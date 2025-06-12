import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer
import json

class TranslationDataset(Dataset):
    def __init__(self, source_texts, target_texts, tokenizer, max_length=512, 
                 src_lang="kor_Hang", tgt_lang="eng_Latn"):
        """
        번역 데이터셋 클래스
        
        Args:
            source_texts: 원본 텍스트 리스트
            target_texts: 번역 텍스트 리스트  
            tokenizer: NLLB 토크나이저
            max_length: 최대 토큰 길이
            src_lang: 소스 언어 코드
            tgt_lang: 타겟 언어 코드
        """
        self.source_texts = source_texts
        self.target_texts = target_texts
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        
    def __len__(self):
        return len(self.source_texts)
    
    def __getitem__(self, idx):
        source_text = str(self.source_texts[idx])
        target_text = str(self.target_texts[idx])
        
        # 소스 언어 설정
        self.tokenizer.src_lang = self.src_lang
        
        # 소스 텍스트 토큰화
        source_encoding = self.tokenizer(
            source_text,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        
        # 타겟 텍스트 토큰화 (with target language token)
        target_encoding = self.tokenizer(
            target_text,
            max_length=self.max_length,
            padding="max_length", 
            truncation=True,
            return_tensors="pt"
        )
        
        # 타겟의 BOS 토큰을 타겟 언어로 설정
        target_ids = target_encoding["input_ids"].squeeze()
        target_ids[0] = self.tokenizer.lang_code_to_id[self.tgt_lang]
        
        return {
            "input_ids": source_encoding["input_ids"].squeeze(),
            "attention_mask": source_encoding["attention_mask"].squeeze(),
            "labels": target_ids
        }

def load_data_from_csv(csv_file):
    """
    CSV 파일에서 번역 데이터 로드
    CSV 형식: source_text, target_text 컬럼 필요
    """
    df = pd.read_csv(csv_file)
    return df["source_text"].tolist(), df["target_text"].tolist()

def load_data_from_json(json_file):
    """
    JSON 파일에서 번역 데이터 로드
    JSON 형식: [{"source": "text1", "target": "text2"}, ...]
    """
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    source_texts = [item["source"] for item in data]
    target_texts = [item["target"] for item in data]
    return source_texts, target_texts

def create_sample_data():
    """
    샘플 데이터 생성 (테스트용)
    """
    sample_data = [
        {"source": "안녕하세요", "target": "Hello"},
        {"source": "오늘 날씨가 좋네요", "target": "The weather is nice today"},
        {"source": "감사합니다", "target": "Thank you"},
        {"source": "죄송합니다", "target": "I'm sorry"},
        {"source": "도움이 필요해요", "target": "I need help"},
        {"source": "좋은 하루 되세요", "target": "Have a good day"},
        {"source": "어디에 있나요?", "target": "Where is it?"},
        {"source": "얼마예요?", "target": "How much is it?"},
        {"source": "이해했습니다", "target": "I understand"},
        {"source": "다시 말해주세요", "target": "Please say it again"}
    ]
    
    source_texts = [item["source"] for item in sample_data]
    target_texts = [item["target"] for item in sample_data]
    return source_texts, target_texts

def prepare_dataloader(source_texts, target_texts, tokenizer, batch_size=4, 
                      src_lang="kor_Hang", tgt_lang="eng_Latn"):
    """
    DataLoader 준비
    """
    dataset = TranslationDataset(
        source_texts, target_texts, tokenizer, 
        src_lang=src_lang, tgt_lang=tgt_lang
    )
    
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    return dataloader

# 테스트 코드
if __name__ == "__main__":
    from transformers import AutoTokenizer
    
    # 토크나이저 로드
    tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
    
    # 샘플 데이터 생성
    source_texts, target_texts = create_sample_data()
    
    # 데이터셋 생성
    dataset = TranslationDataset(source_texts, target_texts, tokenizer)
    
    print(f"데이터셋 크기: {len(dataset)}")
    print(f"첫 번째 샘플:")
    print(dataset[0])
    
    # DataLoader 생성
    dataloader = prepare_dataloader(source_texts, target_texts, tokenizer, batch_size=2)
    
    print(f"\nDataLoader 배치 예시:")
    for batch in dataloader:
        print(f"Input IDs shape: {batch['input_ids'].shape}")
        print(f"Labels shape: {batch['labels'].shape}")
        break 