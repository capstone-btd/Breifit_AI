import json
from pathlib import Path
from typing import List
import torch
from transformers import PreTrainedTokenizerFast, BartForConditionalGeneration


class SummaryGenerator:
    def __init__(self):
        # 1) 모델·토크나이저
        self.tokenizer = PreTrainedTokenizerFast.from_pretrained("gogamza/kobart-base-v2")
        self.model = BartForConditionalGeneration.from_pretrained("gogamza/kobart-base-v2").eval()

        # 2) 장치 할당
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"▶ 사용 중인 장치: {self.device}")
        if torch.cuda.is_available():
            print(f"▶ GPU 모델: {torch.cuda.get_device_name(0)}")
            print(f"▶ GPU 메모리 사용량: {torch.cuda.memory_allocated(0) / 1024**2:.1f}MB")
        self.model.to(self.device)

        # 3) 요약 파라미터
        self.max_length = 256
        self.min_length_ratio = 0.30          # 원문 길이의 20 % (최대 128)
        self.no_repeat_ngram_size = 3
        self.num_beams = 5
        self.batch_size = 8                   # ▼ GPU 메모리에 맞춰 조정

    def _dynamic_min_len(self, input_ids: torch.Tensor) -> int:
        """배치 내 최장 길이를 기준으로 min_length 계산."""
        max_src_len = int(input_ids.ne(self.tokenizer.pad_token_id).sum(dim=1).max())
        return min(128, max(32, int(max_src_len * self.min_length_ratio)))

    @torch.no_grad()
    def summarize_batch(self, texts: List[str]) -> List[str]:
        encodings = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=2048,
            return_token_type_ids=False,
        ).to(self.device)

        min_len = self._dynamic_min_len(encodings["input_ids"])

        summaries = self.model.generate(
            **encodings,
            max_length=self.max_length,
            min_length=min_len,
            no_repeat_ngram_size=self.no_repeat_ngram_size,
            num_beams=self.num_beams,
            length_penalty=1.0,
            early_stopping=True,
        )

        return [self.tokenizer.decode(ids, skip_special_tokens=True) for ids in summaries]


def process_articles():
    input_dir = Path("./articles")
    output_dir = Path("./summarized_articles")
    output_dir.mkdir(exist_ok=True)

    summarizer = SummaryGenerator()

    files = sorted(input_dir.glob("naver_*.json"))
    batch, paths = [], []

    for fp in files:
        with open(fp, encoding="utf-8") as f:
            content = json.load(f)["content"]
        batch.append(content)
        paths.append(fp.name)

        # 배치 크기 도달 or 마지막 파일
        if len(batch) == summarizer.batch_size or fp == files[-1]:
            print(f"▶ 배치 {paths[0]} … {paths[-1]}  ({len(batch)}건)")
            summaries = summarizer.summarize_batch(batch)

            for art_text, summ_text, fname in zip(batch, summaries, paths):
                out_path = output_dir / fname
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump({"original": art_text, "summary": summ_text},
                              out_f, ensure_ascii=False, indent=2)
                print(f"  ✔ 저장: {out_path.name}")

            # 메모리 정리 & 초기화
            batch.clear()
            paths.clear()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()


if __name__ == "__main__":
    process_articles()
