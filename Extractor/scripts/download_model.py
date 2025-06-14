import os
import sys
from huggingface_hub import snapshot_download

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def download_models():
    """
    NLLB 모델 미리 받아오는 코드로, 이거는 DockerFile에서 실행되는 코드임.
    """
    # Define model repository and local directory
    models_to_download = {
        'facebook/nllb-200-1.3B': 'models/translation/nllb-200-1.3B',
    }

    # Download models from Hugging Face
    for repo_id, local_dir in models_to_download.items():
        full_path = os.path.join(project_root, local_dir)
        os.makedirs(full_path, exist_ok=True)
        print(f"Downloading model from {repo_id} to {full_path}")
        
        if os.path.exists(os.path.join(full_path, 'model.safetensors')) or os.path.exists(os.path.join(full_path, 'pytorch_model.bin')):
            print(f"Model already exists in {full_path}. Skipping download.")
            continue

        snapshot_download(repo_id=repo_id, local_dir=full_path, local_dir_use_symlinks=False)
        print(f"Model downloaded successfully to {full_path}")


if __name__ == "__main__":
    download_models() 