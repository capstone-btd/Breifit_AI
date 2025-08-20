"""
단일 기사 텍스트를 입력받아 gpt-oss-20b 모델로 요약(재작성)을 생성합니다.
사용법:
python scripts/run_summarization_by_gpt.py --text_file sample.txt
"""
import os
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import argparse
import pathlib
import textwrap

os.environ['HF_HOME'] = '/home/bobo9245/projects/hf_cache'
os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '1'


def summarize_with_gpt(article_path):
    """gpt-oss-20b 모델을 사용하여 텍스트 파일을 읽어 기사 형식으로 재작성하고, 최종 결과만 stdout으로 출력합니다."""
    
    # 1. 모델 및 토크나이저 불러오기
    model_id = "openai/gpt-oss-20b"
    print(f"'{model_id}' 모델과 토크나이저를 불러옵니다...", file=sys.stderr)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model.eval()
    except Exception as e:
        print(f"모델 로딩 중 오류 발생: {e}", file=sys.stderr)
        return

    # 2. 텍스트 파일 읽기
    try:
        document = pathlib.Path(article_path).read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"오류: 파일 경로를 찾을 수 없습니다 - {article_path}", file=sys.stderr)
        return
    except Exception as e:
        print(f"파일 읽기 중 오류 발생: {e}", file=sys.stderr)
        return

    # 3. 프롬프트 구성
    prompt_content = f"""당신은 주어진 '원본 본문'을 최종 결과물로 가공하는 전문 텍스트 가공자이다. 당신의 유일한 임무는 아래의 '엄격한 가이드라인'을 완벽하게 준수하여 '완성된 기사 본문'만을 출력하는 것이다.

    **[엄격한 가이드라인]**
    1.  **절대적인 출력 형식:** 당신의 최종 응답은 **오직 [완성된 기사 본문]**이어야 한다. 제목, 부제, 당신의 생각, 분석 과정, 노트, 설명 등 그 어떤 추가 텍스트도 절대로 포함해서는 안 된다. 또한, 특수 기호를 사용하지 않는다.
    2.  **구조:** 3~5개의 문단으로 구성되며, 각 문단은 두 번의 줄 바꿈(\n\n)으로 구분된다.
    3.  **내용:** '원본 본문'의 핵심 사실만을 사용해 객관적이고 중립적으로 재구성한다. 주관적 해석이나 감정적 표현은 완전히 배제한다. 추가적으로, 사람들의 직위, 직책, 소속 등 기사에 포함된 정보는 절대로 삭제하지 않는다.
    4.  **문체:** 모든 문장은 '~이다', '~했다' 와 같은 사실적이고 간결한 서술체(해라체)로 작성한다. '~입니다', '~습니다'와 같은 높임말(하십시오체)은 절대 사용하지 않는다.
    5.  **분량:** 전체 본문은 공백 포함 500자 ~ 700자 사이로 작성한다.
    6.  **여러 기사 처리:** '원본 본문'에 기사가 여러 개 포함된 것으로 보이면, 각 내용의 핵심을 종합하여 **하나의 일관된 기사로 합쳐서 작성**해야 한다.

    ---

    ### 과제
    [원본 본문]
    {document}
    ---
    이제, 모든 가이드라인과 예시를 완벽히 준수하여 다른 어떤 설명도 없이 '완성된 기사 본문'의 텍스트만 즉시 시작하라.
    [완성된 기사 본문]
    """
    messages = [{"role": "user", "content": prompt_content}]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    
    # 4. 추론 수행
    print("\n--- 추론 시작 ---", file=sys.stderr)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    summary = ""
    try:
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=6000,
                eos_token_id=tokenizer.eos_token_id,
                do_sample=True,
                temperature=0.4,
                repetition_penalty=1.2,
                top_k=50,
                top_p=0.95
            )
        
        output_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # 5. 결과 파싱 (inference_gpt.py 방식 적용)
        if "assistantfinal" in output_text:
            summary = output_text.split("assistantfinal")[-1].strip()
        elif "<|assistant|>" in output_text:
            summary = output_text.split("<|assistant|>")[-1].strip()
        else:
            # 두 마커가 모두 없는 경우, 모델의 전체 출력을 그대로 사용합니다.
            summary = output_text

    except Exception as e:
        print(f"추론 중 오류 발생: {e}", file=sys.stderr)

    # 6. 최종 결과물만 표준 출력(stdout)으로 인쇄
    print(summary.strip())
    
    # 7. 상세 로그는 표준 에러(stderr)로 인쇄
    print("\n--- 추론 종료 ---", file=sys.stderr)
    print("\n◆ 원본 본문 (stderr 로그)\n" + textwrap.fill(document, 60), file=sys.stderr)
    print("\n◆ 생성된 기사 본문 (stderr 로그)\n" + textwrap.fill(summary, 60), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="GPT-OSS-20B 모델을 사용하여 기사를 재작성합니다.")
    parser.add_argument("--text_file", type=str, required=True, help="재작성할 기사 본문이 담긴 텍스트 파일 경로")
    args = parser.parse_args()
    
    summarize_with_gpt(args.text_file)


if __name__ == "__main__":
    main()
