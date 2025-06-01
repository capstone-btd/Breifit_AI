import asyncio
import json
import os
import subprocess
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict, Any

app = FastAPI()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RUN_COLLECTION_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "run_collection.py")
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

async def run_script():
    """run_collection.py 스크립트를 실행합니다."""
    process = await asyncio.create_subprocess_exec(
        "python", RUN_COLLECTION_SCRIPT_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        print(f"스크립트 실행 오류: {stderr.decode()}")
        return False
    print(stdout.decode())
    return True

def get_all_collected_data() -> List[Dict[str, Any]]:
    """data/raw 폴더의 모든 JSON 파일 내용을 읽어 리스트로 반환합니다."""
    all_data = []
    if not os.path.exists(RAW_DATA_DIR):
        return all_data

    for site_name in os.listdir(RAW_DATA_DIR):
        site_path = os.path.join(RAW_DATA_DIR, site_name)
        if os.path.isdir(site_path):
            for category_name in os.listdir(site_path):
                category_path = os.path.join(site_path, category_name)
                if os.path.isdir(category_path):
                    for filename in os.listdir(category_path):
                        if filename.endswith(".json"):
                            file_path = os.path.join(category_path, filename)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    all_data.append(data)
                            except Exception as e:
                                print(f"Error reading or parsing JSON file {file_path}: {e}")
    return all_data

@app.get("/collect", response_model=List[Dict[str, Any]])
async def collect_and_get_data():
    """
    뉴스 기사 수집 스크립트를 실행하고, 수집된 모든 데이터를 JSON 형태로 반환합니다.
    """
    print("기사 수집 스크립트 실행 시작...")
    success = await run_script()
    if not success:
        return JSONResponse(status_code=500, content={"message": "데이터 수집 스크립트 실행에 실패했습니다."})
    
    print("수집된 데이터 읽기 시작...")
    collected_data = get_all_collected_data()
    
    if not collected_data:
        return JSONResponse(status_code=404, content={"message": "수집된 데이터가 없습니다."})
        
    print(f"총 {len(collected_data)}개의 기사 데이터를 반환합니다.")
    return collected_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 