"""
JSON 기사(1 or N개) → 요약
사용:  python scripts/generate.py sample.json
"""
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import argparse, pathlib, json, re
from typing import List

CKPT   = "models/kobart-sum/final"
DEVICE = "cuda"

# ───────────── 반복 꼬리 후처리 ─────────────
SHORT_SENT_RE = re.compile(r'^[가-힣]{1,10}다[.!?]?$')   # “했다.”, “밝혔다.”
MIN_LEN       = 8                                        # 8자 미만이면 삭제

def _clean_tail(text: str) -> str:
    """요약 끝부분의 의미 없는 짧은 문장(동사+다) 반복을 제거한다."""
    sents = re.split(r'(?<=[.!?])\s+', text)              # 단순 문장 분리
    while sents and (
        len(sents[-1].strip()) < MIN_LEN
        or SHORT_SENT_RE.match(sents[-1].strip())
        or (len(sents) > 1 and sents[-1] == sents[-2])    # 바로 앞 문장과 동일
    ):
        sents.pop()
    return " ".join(sents)

# ───────────── JSON 로딩 ─────────────
def load_json(path: str) -> str:
    obj = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))

    def clean(txt: str) -> str:
        txt = re.sub(r'\s+\n', '\n', txt.strip())
        return re.sub(r'\n{3,}', '\n\n', txt)

    if isinstance(obj, dict):            # 단일 기사
        return clean(obj["body"])

    if isinstance(obj, list):            # 여러 기사
        merged = "\n\n".join(art["body"].strip() for art in obj)
        return clean(merged)

    raise ValueError("지원하지 않는 JSON 형식입니다.")

# ───────────── 요약 함수 ─────────────
def generate_summary(text: str, max_len: int = 1024) -> str:
    tok   = AutoTokenizer.from_pretrained(CKPT)
    model = AutoModelForSeq2SeqLM.from_pretrained(CKPT).to(DEVICE)

    inputs = tok(text, return_tensors="pt",
                 truncation=True, max_length=1024).to(DEVICE)
    inputs.pop("token_type_ids", None)

    out = model.generate(**inputs,
                         num_beams=4,
                         max_length=max_len,
                         length_penalty=1.2)
    summary = tok.decode(out[0], skip_special_tokens=True)
    return _clean_tail(summary)          # ← 후처리

# ───────────── 초과 길이 처리 ─────────────
def smart_summarize(long_text: str) -> str:
    tok = AutoTokenizer.from_pretrained(CKPT)
    if len(tok(long_text)["input_ids"]) <= 1024:
        return generate_summary(long_text)

    # 문단 단위 슬라이딩-윈도 요약 → 요약의 요약
    paras, cur, chunks = long_text.split("\n\n"), [], []
    for p in paras:
        cur.append(p)
        if len(tok("\n\n".join(cur))["input_ids"]) > 1024:
            chunks.append("\n\n".join(cur)); cur = []
    if cur:
        chunks.append("\n\n".join(cur))

    stitched = "\n".join(generate_summary(c, 512) for c in chunks)
    return generate_summary(stitched, 512)  # 최종도 후처리 포함

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
