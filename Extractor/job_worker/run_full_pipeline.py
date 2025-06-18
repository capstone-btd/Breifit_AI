import subprocess
import sys
import os

def main():
    """
    기능:
    데이터 수집 및 처리 파이프라인 전체를 실행. run_collection.py, run_processing.py 실행

    input:
    없음

    output:
    없음
    """
    try:
        collection_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'run_collection.py')
        print("Starting data collection...")
        subprocess.run([sys.executable, collection_script_path], check=True)
        print("Data collection finished successfully.")

        processing_script_path = os.path.join(os.path.dirname(__file__), 'scripts', 'run_processing.py')
        print("Starting data processing...")
        subprocess.run([sys.executable, processing_script_path], check=True)
        print("Data processing finished successfully.")

        print("Full pipeline completed successfully.")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during script execution: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Add the project root to the Python path to allow for absolute imports
    # from src, DB, etc.
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(project_root)
    main() 