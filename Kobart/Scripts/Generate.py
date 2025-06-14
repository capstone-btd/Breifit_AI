"""
단일 기사 텍스트를 입력받아 요약 생성
python scripts/generate.py --text_file sample.txt
"""
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import argparse, pathlib, textwrap

CKPT = "models/kobart-sum/final"      # 학습 후 경로

def summarize(article_path):
    text = pathlib.Path(article_path).read_text(encoding="utf-8").strip()
    tok  = AutoTokenizer.from_pretrained(CKPT)
    model= AutoModelForSeq2SeqLM.from_pretrained(CKPT).to("cuda")

    inputs = tok(text, return_tensors="pt",
                 truncation=True, max_length=1024).to("cuda")
    out = model.generate(**inputs,
                         num_beams=4,
                         max_length=128,
                         length_penalty=1.2)
    summary = tok.decode(out[0], skip_special_tokens=True)
    print("\n◆ Generated Summary\n" + textwrap.fill(summary, 60))

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--text_file", required=True)
    summarize(p.parse_args().text_file)
