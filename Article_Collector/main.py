from projects.Extractor.jw_gemini.src.processing.summarizer import get_refiner

def main():
    """
    GeminiAPIRefiner를 사용하여 텍스트 정제를 테스트하는 메인 함수.
    """
    # 1. Refiner 인스턴스를 가져옵니다.
    #    (API 키가 환경 변수에 설정되어 있어야 합니다.)
    refiner = get_refiner()

    if not refiner:
        print("Refiner 초기화에 실패했습니다. GEMINI_API_KEY 환경 변수를 확인하세요.")
        return

    # 2. 정제할 샘플 텍스트
    sample_text = """
    연구개발 예산 배분과 관련해 선택과 집중, 대형화와 같은 기존 기조를 유지하면서도 다양성과 안정성, 자율성을 보장하겠다고 밝혔다. 
    지난두 해 전 급작스러운 R&D 예산 삭감 결정으로 과학기술계가 혼란에 빠졌다. 
    선택과 집중을 위해 12종류의 큰 나무들만 남겨놓고, 나무 그늘 밑에서 펼쳐지는 다양한 작은 묘목들과 꽃들이 만드는 생태계에 물을 주지 않으면 결국 큰 나무들도 죽게 된다고 설명했다.
    """

    # 3. 텍스트 정제 실행
    print("="*20 + " 원본 텍스트 " + "="*20)
    print(sample_text.strip())
    print("\n" + "="*20 + " Gemini 정제 시작... " + "="*20)

    refined_text = refiner.refine_text(sample_text)

    print("\n" + "="*20 + " 정제된 텍스트 " + "="*20)
    print(refined_text)
    print("="*55)


if __name__ == "__main__":
    main() 