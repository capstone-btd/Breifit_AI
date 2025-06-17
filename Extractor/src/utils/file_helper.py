import json
import os
import aiofiles
from datetime import datetime
from typing import List, Dict, Any

async def save_json_async(data: Any, filepath: str):
    """주어진 데이터를 JSON 파일로 비동기적으로 저장합니다."""
    try:
        # 파일 경로에서 디렉토리를 추출하고, 해당 디렉토리가 없으면 생성합니다.
        directory = os.path.dirname(filepath)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            print(f"디렉토리 생성: {directory}")

        async with aiofiles.open(filepath, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))
        print(f"JSON 파일 저장 완료: {filepath}")
    except Exception as e:
        print(f"JSON 파일 저장 실패 ({filepath}): {e}")

def load_json(filepath: str) -> Any | None:
    """JSON 파일을 로드하여 내용을 반환합니다."""
    try:
        if not os.path.exists(filepath):
            print(f"JSON 파일 없음: {filepath}")
            return None
        with open(filepath, mode='r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"JSON 파일 로드 완료: {filepath}")
        return data
    except Exception as e:
        print(f"JSON 파일 로드 실패 ({filepath}): {e}")
        return None

def get_output_path(base_dir: str, site_name: str, category_name: str, filename: str, collection_time_str: str) -> str:
    """
    기능: 일관된 형식으로 출력 파일 경로를 생성한다.
    input: 기본 디렉토리(base_dir), 사이트 이름(site_name), 카테고리 이름(category_name), 파일명(filename), 수집 시간 문자열(collection_time_str)
    output: 최종 파일 경로 (str)
    """
    if category_name:
        path = os.path.join(base_dir, collection_time_str, category_name)
    else:
        path = os.path.join(base_dir, collection_time_str)
        
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    return os.path.join(path, filename)

def remove_nbsp(text: str) -> str:
    """
    Non-breaking space &nbsp; (`\xa0`) 문자를 일반 공백으로 변환하고 양쪽 공백을 제거합니다.
    """
    return text.replace("\xa0", " ").strip()