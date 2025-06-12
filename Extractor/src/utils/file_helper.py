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


# slugify 함수를 cnn_collector.py에서 여기로 옮겨올 수 있습니다.
# 다른 곳에서도 파일명 생성 등에 필요할 수 있기 때문입니다.
import re
def slugify(text: Any) -> str:
    """
    입력 텍스트를 파일명이나 URL 슬러그로 사용하기 안전한 형태로 변환합니다.
    None이나 빈 문자열이 들어오면 빈 문자열을 반환합니다.
    숫자도 문자열로 변환하여 처리합니다.
    """
    if text is None: # 명시적으로 None을 확인
        return ""
    text_str = str(text) # 다른 타입일 경우 문자열로 변환
    if not text_str.strip(): # 공백만 있는 문자열도 빈 문자열로 처리
        return ""
    # 한글, 영문, 숫자, 공백을 제외한 문자 제거. 하이픈은 유지.
    # 오류 수정: [^\w\s-가-힣ㄱ-ㅎㅏ-ㅣ] -> [^\w가-힣ㄱ-ㅎㅏ-ㅣ\s-]
    text_str = re.sub(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ\s-]', '', text_str.lower()) # 하이픈을 범위 지정 문자 뒤로 이동
    # 연속되는 공백이나 하이픈을 단일 하이픈으로 변경
    text_str = re.sub(r'[\s-]+', '-', text_str).strip('-_')
    return text_str 