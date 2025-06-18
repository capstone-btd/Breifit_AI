import os
from transformers import AutoTokenizer

def fix_tokenizer_files(model_path, original_model_name="gogamza/kobart-summarization"):
    """
    Hugging Face Hub에서 토크나이저를 로드하여 로컬 경로에 저장함으로써,
    손상 가능성이 있는 기존 토크나이저 파일을 덮어씁니다.
    
    Args:
        model_path (str): 모델 및 토크나이저가 저장된 로컬 경로.
        original_model_name (str): 토크나이저를 로드할 Hugging Face Hub의 원본 모델 이름.
    """
    print(f"'{original_model_name}'으로부터 원본 토크나이저를 로드합니다...")
    try:
        # Hub에서 토크나이저 로드
        tokenizer = AutoTokenizer.from_pretrained(original_model_name)
        
        # 대상 디렉토리 존재 확인 및 생성
        os.makedirs(model_path, exist_ok=True)
        
        # 로컬 경로에 토크나이저 저장. 기존 파일을 덮어씁니다.
        tokenizer.save_pretrained(model_path)
        
        print(f"'{model_path}' 경로에 새로운 토크나이저 파일을 성공적으로 저장했습니다.")
        print("기존의 tokenizer.json과 관련 파일들을 덮어썼습니다.")
        
    except Exception as e:
        print(f"토크나이저를 수정하는 중 오류가 발생했습니다: {e}")
        print("Hugging Face Hub 모델 이름이 올바른지, 인터넷 연결이 정상적인지 확인해주세요.")

if __name__ == "__main__":
    # 이 스크립트는 Extractor/scripts/ 폴더에 있다고 가정합니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(current_dir)
    summarization_model_path = os.path.join(PROJECT_ROOT, 'models', 'summarization')
    
    print(f"타겟 경로: {summarization_model_path}")
    fix_tokenizer_files(model_path=summarization_model_path) 