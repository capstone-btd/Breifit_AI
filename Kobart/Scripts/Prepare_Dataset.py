"""
원본 combined_content_summary.json ▸ train/valid/test JSONL 분할 스크립트
실행: python scripts/prepare_dataset.py --seed 42 --split 0.8 0.1 0.1
"""
import json, random, argparse, pathlib

def main(all_json, out_dir, split, seed):
    random.seed(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    articles = json.load(open(all_json, "r", encoding="utf-8"))["articles"]
    random.shuffle(articles)
    n = len(articles)
    train_end = int(split[0] * n)
    valid_end = train_end + int(split[1] * n)

    subsets = {
        "train": articles[:train_end],
        "valid": articles[train_end:valid_end],
        "test":  articles[valid_end:]
    }

    for name, rows in subsets.items():
        with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8") as w:
            for r in rows:
                json.dump(
                    {
                        "id": r["id"],
                        "text":  r["content"].strip(),
                        "summary": r["summary"].strip(),
                    },
                    w,
                    ensure_ascii=False,
                )
                w.write("\n")
    print(f"Saved: {[f'{k}={len(v)}' for k,v in subsets.items()]}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--all_json", default="../Dataset/summarized_articles/combined_content_summary.json")
    p.add_argument("--out_dir",  default="Data")
    p.add_argument("--split",    nargs=3, type=float, default=[0.8, 0.1, 0.1])
    p.add_argument("--seed",     type=int, default=42)
    args = p.parse_args()
    main(pathlib.Path(args.all_json),
         pathlib.Path(args.out_dir),
         args.split,
         args.seed)
