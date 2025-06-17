"""
JSON 기사(1 or N개) → 요약
사용:  python scripts/generate.py sample.json
"""
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import argparse, pathlib, textwrap, json, re
from typing import List

CKPT   = "models/kobart-sum/final"
DEVICE = "cuda"

# ───────────── JSON 로딩 ─────────────
def load_json(path: str) -> str:
    obj = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    def clean(txt: str) -> str:
        txt = re.sub(r'\s+\n', '\n', txt.strip())
        return re.sub(r'\n{3,}', '\n\n', txt)

    if isinstance(obj, dict):                       # 단일 기사
        return clean(obj["body"])

    if isinstance(obj, list):                      # 여러 기사
        merged_bodies: List[str] = []
        for art in obj:
            merged_bodies.append(art["body"].strip())
        return clean("\n\n".join(merged_bodies)) 

    raise ValueError("지원하지 않는 JSON 형식입니다.")

# ───────────── 요약 함수 ─────────────
def generate_summary(text: str, max_len: int = 1024) -> str:
    tok    = AutoTokenizer.from_pretrained(CKPT)
    model  = AutoModelForSeq2SeqLM.from_pretrained(CKPT).to(DEVICE)

    inputs = tok(text, return_tensors="pt", truncation=True, max_length=1024).to(DEVICE)
    inputs.pop("token_type_ids", None)

    out = model.generate(**inputs, num_beams=4, max_length=max_len, length_penalty=1.2)
    return tok.decode(out[0], skip_special_tokens=True)

# ───────────── 초과 길이 처리 ─────────────
def smart_summarize(long_text: str) -> str:
    tok = AutoTokenizer.from_pretrained(CKPT)
    if len(tok(long_text)["input_ids"]) <= 1024:
        return generate_summary(long_text)

    # 문단 단위 슬라이딩-윈도 부분 요약 → 요약의 요약
    paras, cur, chunks = long_text.split("\n\n"), [], []
    for p in paras:
        cur.append(p)
        if len(tok("\n\n".join(cur))["input_ids"]) > 1024:
            chunks.append("\n\n".join(cur)); cur = []
    if cur: chunks.append("\n\n".join(cur))

    stitched = "\n".join(generate_summary(c, 512) for c in chunks)
    return generate_summary(stitched, 512)

# ───────────── CLI ─────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file", help="단일/다중 기사 JSON")
    path = ap.parse_args().json_file

    text    = load_json(path)
    summary = smart_summarize(text)

    print("\n◆ Generated Summary\n" + summary)

if __name__ == "__main__":
    main()
