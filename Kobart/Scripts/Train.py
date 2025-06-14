"""
KoBART 파인튜닝 스크립트.
실행: CUDA_VISIBLE_DEVICES=0 python scripts/train.py --epochs 5
"""
from datasets import load_dataset
from transformers import (AutoTokenizer, AutoModelForSeq2SeqLM,
                          Seq2SeqTrainingArguments, Seq2SeqTrainer)
import evaluate, argparse
import torch

MODEL_NAME = "gogamza/kobart-base-v2"
MAX_INPUT  = 384 //GPU 메모리에 따라 설정해야함. 높을수록 정확도 증가, 기사 원문 보존
MAX_TARGET = 256

def check_gpu():
    print("\n=== GPU 정보 ===")
    print(f"CUDA 사용 가능: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"현재 사용 중인 GPU: {torch.cuda.get_device_name(0)}")
        print(f"GPU 개수: {torch.cuda.device_count()}")
        print(f"현재 GPU 메모리 사용량: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
        print(f"현재 GPU 메모리 캐시: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
    print("===============\n")

def preprocess_fn(examples, tokenizer):
    inputs = tokenizer(
        examples["text"], max_length=MAX_INPUT,
        truncation=True, padding="max_length"
    )
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(
            examples["summary"], max_length=MAX_TARGET,
            truncation=True, padding="max_length"
        )
    inputs["labels"] = labels["input_ids"]
    return inputs

def compute_metrics_fn(eval_pred, tokenizer, rouge):
    preds, labels = eval_pred
    preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
    labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
    scores = rouge.compute(predictions=preds, references=labels, use_stemmer=True)
    return {k: round(v * 100, 2) for k, v in scores.items()}

def main(epochs, batch, grad_accum):
    # GPU 정보 확인
    check_gpu()
    
    tok   = AutoTokenizer.from_pretrained(MODEL_NAME)
    rouge = evaluate.load("rouge")

    ds = load_dataset(
        "json",
        data_files={
            "train": "Data/train.jsonl",
            "validation": "Data/valid.jsonl",
        },
    )
    ds = ds.map(lambda x: preprocess_fn(x, tok), batched=True,
                remove_columns=["id", "text", "summary"])

    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    
    # 모델을 GPU로 명시적으로 이동
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    
    # 모델이 GPU로 이동되었는지 확인
    device = next(model.parameters()).device
    print(f"\n모델이 {device}에서 실행 중입니다.\n")

    args = Seq2SeqTrainingArguments(
        output_dir="models/kobart-sum",
        num_train_epochs=epochs,
        per_device_train_batch_size=batch,
        per_device_eval_batch_size=batch,
        gradient_accumulation_steps=grad_accum,
        learning_rate=3e-5,
        warmup_steps=500,
        eval_steps=1000,
        logging_steps=100,
        save_total_limit=3,
        fp16=True,
        generation_max_length=MAX_TARGET,
        generation_num_beams=4,
        load_best_model_at_end=True,
        metric_for_best_model="rouge2",
        greater_is_better=True,
        save_strategy="no",
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=args,
        train_dataset=ds["train"],
        eval_dataset=ds["validation"],
        tokenizer=tok,
        compute_metrics=lambda p: compute_metrics_fn(p, tok, rouge),
    )

    trainer.train()
    trainer.save_model("models/kobart-sum/final")

if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--epochs", type=int, default=5)
    a.add_argument("--batch",  type=int, default=4)
    a.add_argument("--grad_accum", type=int, default=4)
    main(**vars(a.parse_args()))
