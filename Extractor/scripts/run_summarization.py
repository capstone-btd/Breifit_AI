import asyncio
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.utils.file_helper import load_json, save_json_async
from src.processing.summarizer import summarize_and_extract_keywords

GROUPED_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed', 'grouped_articles')
SUMMARIZED_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed', 'summarized_articles')

def load_all_grouped_articles(grouped_data_dir: str) -> List[Dict[str, Any]]:
    """
    기능: grouped_data_dir에서 모든 그룹화된 기사 데이터들을 로드한다.
    input: 그룹화된 데이터 디렉토리 경로 (str)
    output: 모든 그룹 데이터가 담긴 리스트 (List[Dict[str, Any]])
    """
    all_grouped_data = []
    print(f"그룹화된 기사 로드 시작: {grouped_data_dir}")
    if not os.path.exists(grouped_data_dir):
        print(f"경고: 그룹화된 데이터 디렉토리({grouped_data_dir})가 존재하지 않습니다.")
        return []

    for date_folder in os.listdir(grouped_data_dir):
        date_path = os.path.join(grouped_data_dir, date_folder)
        if not os.path.isdir(date_path): continue

        for filename in os.listdir(date_path):
            if filename.endswith('.json'):
                filepath = os.path.join(date_path, filename)
                group_data = load_json(filepath)
                if group_data:
                    group_data['_filepath'] = filepath
                    all_grouped_data.append(group_data)

    print(f"총 {len(all_grouped_data)}개의 그룹 데이터를 로드했습니다.")
    return all_grouped_data

async def main():
    """
    기능: 그룹화된 기사들을 요약하고 키워드를 추출하여 그 결과를 파일로 저장한다.
    input: 없음
    output: 없음
    """
    print("===== 기사 요약 및 키워드 추출 프로세스 시작 =====")

    grouped_articles = load_all_grouped_articles(GROUPED_DATA_DIR)

    if not grouped_articles:
        print("요약할 그룹 데이터가 없습니다. 프로세스를 종료합니다.")
        return

    summarized_data_list = summarize_and_extract_keywords(grouped_articles)

    if not summarized_data_list:
        print("요약 및 키워드 추출 결과가 없습니다. 프로세스를 종료합니다.")
        return

    print(f"총 {len(summarized_data_list)}개 그룹에 대한 요약/키워드 생성됨. 파일 저장 시작...")

    save_tasks = []
    saved_summary_count = 0
    for summary_item in summarized_data_list:
        group_id = summary_item.get('group_id')
        if not group_id:
            print(f"경고: group_id가 없는 요약 데이터가 있어 건너뜁니다: {summary_item.get('summary', '')[:50]}...")
            continue

        today_date_str = datetime.now().strftime("%Y-%m-%d")
        summary_dir = os.path.join(SUMMARIZED_DATA_DIR, today_date_str)

        output_filename = f"{group_id}_summary.json"
        if not os.path.exists(summary_dir):
            os.makedirs(summary_dir)
        filepath = os.path.join(summary_dir, output_filename)

        save_tasks.append(save_json_async(summary_item, filepath))
        saved_summary_count += 1

    await asyncio.gather(*save_tasks)
    print(f"총 {saved_summary_count}개의 요약된 기사 정보를 저장했습니다.")
    print("===== 기사 요약 및 키워드 추출 프로세스 완료 =====")

if __name__ == '__main__':
    asyncio.run(main()) 