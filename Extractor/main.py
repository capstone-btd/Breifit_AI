import asyncio
import json
import os
import subprocess
import sys
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from typing import List, Dict, Any

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI()

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RUN_COLLECTION_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "run_collection.py")
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")

async def run_script():
    """
    기능: run_collection.py 스크립트를 비동기 서브프로세스로 실행하고 결과를 반환한다.
    input: 없음
    output: 스크립트 실행 성공 여부 (bool)
    """
    process = await asyncio.create_subprocess_exec(
        sys.executable, RUN_COLLECTION_SCRIPT_PATH,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if stdout:
        print("--- 스크립트 출력(STDOUT) ---")
        print(stdout.decode('utf-8', errors='ignore'))
        print("--------------------------")

    if stderr:
        print("--- 스크립트 오류(STDERR) ---")
        print(stderr.decode('utf-8', errors='ignore'))
        print("--------------------------")


    if process.returncode != 0:
        print(f"스크립트 실행 오류: 종료 코드 {process.returncode}")
        return False
    
    print("스크립트 실행 완료")
    return True

def get_all_collected_data() -> List[Dict[str, Any]]:
    """
    기능: data/raw 폴더의 모든 JSON 파일 내용을 읽어 리스트로 반환한다.
    input: 없음
    output: 모든 기사 데이터가 담긴 리스트 (List[Dict[str, Any]])
    """
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
    기능: 데이터 수집 스크립트를 실행하고, 수집된 모든 데이터를 JSON으로 반환한다.
    input: 없음 (HTTP GET 요청)
    output: 수집된 전체 기사 데이터 (JSONResponse)
    """
    print("기사 수집 스크립트 실행 시작...")
    try:
        success = await run_script()
        if not success:
            return JSONResponse(status_code=500, content={"message": "데이터 수집 스크립트 실행에 실패했습니다. 터미널 로그를 확인해주세요."})
        
        print("수집된 데이터 읽기 시작...")
        collected_data = get_all_collected_data()
        
        if not collected_data:
            return JSONResponse(status_code=404, content={"message": "수집된 데이터가 없습니다."})
            
        print(f"총 {len(collected_data)}개의 기사 데이터를 반환합니다.")
        return collected_data
    except Exception as e:
        print(f"'/collect' 엔드포인트에서 예기치 않은 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"message": f"서버 내부 오류가 발생했습니다: {e}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)