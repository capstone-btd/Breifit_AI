import torch
import torch.nn as nn
from torch.optim import AdamW
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM,
    get_linear_schedule_with_warmup
)
from torch.utils.data import DataLoader
from tqdm import tqdm
import os
import json
from datetime import datetime

# 데이터 준비 모듈 import
from data_preparation import TranslationDataset, create_sample_data, load_data_from_csv, load_data_from_json

class NLLBFineTuner:
    def __init__(self, model_name="facebook/nllb-200-distilled-600M", 
                 src_lang="kor_Hang", tgt_lang="eng_Latn"):
        """
        NLLB 파인튜닝 클래스
        """
        self.model_name = model_name
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        print(f"사용 디바이스: {self.device}")
        print(f"모델 로딩: {model_name}")
        
        # 모델과 토크나이저 로드
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.to(self.device)
        
        print("모델 로딩 완료!")
        
    def prepare_data(self, source_texts, target_texts, batch_size=4, train_split=0.8):
        """
        훈련/검증 데이터 준비
        """
        # 데이터 분할
        split_idx = int(len(source_texts) * train_split)
        
        train_sources = source_texts[:split_idx]
        train_targets = target_texts[:split_idx]
        val_sources = source_texts[split_idx:]
        val_targets = target_texts[split_idx:]
        
        # 데이터셋 생성
        train_dataset = TranslationDataset(
            train_sources, train_targets, self.tokenizer,
            src_lang=self.src_lang, tgt_lang=self.tgt_lang
        )
        
        val_dataset = TranslationDataset(
            val_sources, val_targets, self.tokenizer,
            src_lang=self.src_lang, tgt_lang=self.tgt_lang
        )
        
        # DataLoader 생성
        self.train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        self.val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        print(f"훈련 데이터: {len(train_dataset)} 샘플")
        print(f"검증 데이터: {len(val_dataset)} 샘플")
        
    def train_epoch(self, optimizer, scheduler):
        """
        한 에포크 훈련
        """
        self.model.train()
        total_loss = 0
        
        progress_bar = tqdm(self.train_loader, desc="Training")
        
        for batch in progress_bar:
            # GPU로 데이터 이동
            input_ids = batch["input_ids"].to(self.device)
            attention_mask = batch["attention_mask"].to(self.device)
            labels = batch["labels"].to(self.device)
            
            # Forward pass
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            
            loss = outputs.loss
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            
            total_loss += loss.item()
            progress_bar.set_postfix({"loss": loss.item()})
            
        return total_loss / len(self.train_loader)
    
    def validate_epoch(self):
        """
        한 에포크 검증
        """
        self.model.eval()
        total_loss = 0
        
        with torch.no_grad():
            for batch in tqdm(self.val_loader, desc="Validation"):
                input_ids = batch["input_ids"].to(self.device)
                attention_mask = batch["attention_mask"].to(self.device)
                labels = batch["labels"].to(self.device)
                
                outputs = self.model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                total_loss += outputs.loss.item()
                
        return total_loss / len(self.val_loader)
    
    def train(self, source_texts, target_texts, epochs=3, learning_rate=5e-5, 
              batch_size=4, warmup_steps=100, save_path="./finetuned_nllb"):
        """
        모델 훈련
        """
        print("데이터 준비 중...")
        self.prepare_data(source_texts, target_texts, batch_size)
        
        # 옵티마이저와 스케줄러 설정
        optimizer = AdamW(self.model.parameters(), lr=learning_rate)
        
        total_steps = len(self.train_loader) * epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer, 
            num_warmup_steps=warmup_steps,
            num_training_steps=total_steps
        )
        
        # 훈련 기록
        train_losses = []
        val_losses = []
        
        print(f"훈련 시작 - 총 {epochs} 에포크")
        
        for epoch in range(epochs):
            print(f"\n에포크 {epoch + 1}/{epochs}")
            
            # 훈련
            train_loss = self.train_epoch(optimizer, scheduler)
            train_losses.append(train_loss)
            
            # 검증
            val_loss = self.validate_epoch()
            val_losses.append(val_loss)
            
            print(f"훈련 손실: {train_loss:.4f}")
            print(f"검증 손실: {val_loss:.4f}")
            
            # 모델 저장 (각 에포크마다)
            epoch_save_path = f"{save_path}_epoch_{epoch + 1}"
            self.save_model(epoch_save_path)
            
        # 최종 모델 저장
        self.save_model(save_path)
        
        # 훈련 기록 저장
        training_log = {
            "train_losses": train_losses,
            "val_losses": val_losses,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "batch_size": batch_size
        }
        
        with open(f"{save_path}/training_log.json", "w") as f:
            json.dump(training_log, f, indent=2)
            
        print(f"\n훈련 완료! 모델이 {save_path}에 저장되었습니다.")
        
    def save_model(self, save_path):
        """
        모델 저장
        """
        os.makedirs(save_path, exist_ok=True)
        self.model.save_pretrained(save_path)
        self.tokenizer.save_pretrained(save_path)
        
    def translate(self, text):
        """
        번역 함수
        """
        self.model.eval()
        self.tokenizer.src_lang = self.src_lang
        
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            generated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=self.tokenizer.lang_code_to_id[self.tgt_lang],
                max_length=512,
                num_beams=5,
                early_stopping=True
            )
        
        result = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]
        return result

# 메인 실행 코드
if __name__ == "__main__":
    # 파인튜너 초기화
    fine_tuner = NLLBFineTuner()
    
    # 샘플 데이터로 테스트 (실제로는 더 많은 데이터 필요)
    source_texts, target_texts = create_sample_data()
    
    # 파인튜닝 전 번역 테스트
    print("=== 파인튜닝 전 번역 ===")
    test_text = "안녕하세요, 오늘 날씨가 좋네요."
    before_result = fine_tuner.translate(test_text)
    print(f"입력: {test_text}")
    print(f"출력: {before_result}")
    
    # 파인튜닝 실행
    print("\n=== 파인튜닝 시작 ===")
    fine_tuner.train(
        source_texts=source_texts,
        target_texts=target_texts,
        epochs=5,  # 실제로는 더 많은 에포크 필요
        learning_rate=5e-5,
        batch_size=2  # GPU 메모리에 따라 조정
    )
    
    # 파인튜닝 후 번역 테스트
    print("\n=== 파인튜닝 후 번역 ===")
    after_result = fine_tuner.translate(test_text)
    print(f"입력: {test_text}")
    print(f"출력: {after_result}") 