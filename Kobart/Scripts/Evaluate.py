"""
test.jsonl 전체에 대해 ROUGE-L/1/2 평가
python scripts/evaluate.py
"""
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import evaluate, tqdm

CKPT = "models/kobart-sum/final"
MAX_INPUT, MAX_TARGET = 1024, 128

def main():
    ds = load_dataset("json", data_files={"test": "Data/test.jsonl"})["test"]
    tok = AutoTokenizer.from_pretrained(CKPT)
    model = AutoModelForSeq2SeqLM.from_pretrained(CKPT).to("cuda")
    rouge = evaluate.load("rouge")

    preds, refs = [], []
    for sample in tqdm.tqdm(ds, desc="Generating"):
        inputs = tok(sample["text"], 
                    return_tensors="pt",
                    truncation=True, 
                    max_length=MAX_INPUT,
                    return_token_type_ids=False).to("cuda")
        out = model.generate(**inputs, num_beams=4, max_length=MAX_TARGET)
        preds.append(tok.decode(out[0], skip_special_tokens=True))
        refs.append(sample["summary"])

    scores = rouge.compute(predictions=preds, references=refs, use_stemmer=True)
    print({k: round(v * 100, 2) for k, v in scores.items()})

if __name__ == "__main__":
    main()
