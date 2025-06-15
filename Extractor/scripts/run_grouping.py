import asyncio
import os
import sys
from datetime import datetime
from typing import List, Dict, Any

from slugify import slugify

# 프로젝트 루트 경로 설정
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from src.utils.file_helper import load_json, save_json_async, get_output_path
from src.processing.article_grouper import group_articles # 그룹화 함수 임포트

RAW_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
GROUPED_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed', 'grouped_articles')

def load_all_raw_articles(raw_data_dir: str) -> List[Dict[str, Any]]:
    """
    기능: raw_data_dir에서 모든 수집된 기사들을 로드한다.
    input: 원본 데이터 디렉토리 경로 (str)
    output: 모든 기사 데이터가 담긴 리스트 (List[Dict[str, Any]])
    """
    all_articles = []
    print(f"원본 기사 로드 시작: {raw_data_dir}")
    if not os.path.exists(raw_data_dir):
        print(f"경고: 원본 데이터 디렉토리({raw_data_dir})가 존재하지 않습니다.")
        return []

    for site_name in os.listdir(raw_data_dir):
        site_path = os.path.join(raw_data_dir, site_name)
        if not os.path.isdir(site_path): continue

        for category_name in os.listdir(site_path):
            category_path = os.path.join(site_path, category_name)
            if not os.path.isdir(category_path): continue

            for date_folder in os.listdir(category_path):
                date_path = os.path.join(category_path, date_folder)
                if not os.path.isdir(date_path): continue

                for filename in os.listdir(date_path):
                    if filename.endswith('.json'):
                        filepath = os.path.join(date_path, filename)
                        article_data = load_json(filepath)
                        if article_data:
                            # 그룹화를 위해 파일 경로 정보도 추가하면 유용할 수 있음
                            article_data['_filepath'] = filepath 
                            all_articles.append(article_data)
    
    print(f"총 {len(all_articles)}개의 원본 기사를 로드했습니다.")
    return all_articles

async def main():
    """
    기능: 수집된 모든 기사를 로드하여 유사한 주제끼리 그룹화하고, 그 결과를 파일로 저장한다.
    input: 없음
    output: 없음
    """
    print("===== 기사 그룹핑 프로세스 시작 =====")

    # 1. 모든 원본 기사 로드
    raw_articles = load_all_raw_articles(RAW_DATA_DIR)

    if not raw_articles:
        print("그룹화할 기사가 없습니다. 프로세스를 종료합니다.")
        return

    # 2. 기사 그룹핑 실행
    # group_articles 함수는 동기 함수이므로 그대로 호출합니다.
    # 만약 group_articles가 비동기가 된다면 await 사용 필요.
    grouped_article_data_list = group_articles(raw_articles)

    if not grouped_article_data_list:
        print("기사 그룹핑 결과가 없습니다. 프로세스를 종료합니다.")
        return

    print(f"총 {len(grouped_article_data_list)}개의 기사 그룹 생성됨. 파일 저장 시작...")

    # 3. 그룹화된 결과 저장
    # 그룹 ID가 없다면 생성 (group_articles 함수에서 group_id를 반환한다고 가정)
    # 파일명은 그룹의 대표 제목이나 ID를 기반으로 생성
    save_tasks = []
    saved_group_count = 0
    for group_data in grouped_article_data_list:
        group_id = group_data.get('group_id')
        if not group_id: # group_id가 없는 경우 (article_grouper.py의 임시 로직 고려)
            # 임시 ID 생성 또는 대표 제목 기반으로 생성
            rep_title = group_data.get('representative_title', 'untitled_group')
            if rep_title:
                group_id = slugify(rep_title)
            else:
                group_id = f"group_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{saved_group_count}"
            group_data['group_id'] = group_id # 데이터에도 group_id 업데이트

        # 그룹 저장 시, 사이트명이나 카테고리명이 필요 없을 수 있음. 
        # get_output_path의 site_name, category_name 인자를 None 또는 빈 문자열로 처리하도록 수정하거나
        # 그룹핑 단계용 새로운 경로 생성 함수를 file_helper에 추가할 수 있음.
        # 여기서는 site_name="all_sites", category_name="all_categories" 등으로 단순화하거나
        # 날짜 기반으로만 저장.
        
        # get_output_path의 category_name 인자는 실제 폴더 구조에 맞게 조정 필요.
        # 그룹화된 데이터는 특정 카테고리에 종속되지 않을 수 있으므로, 날짜별로만 저장하거나,
        # group_id 자체를 파일명으로 사용하고 단일 폴더에 저장할 수 있음.
        # 여기서는 오늘 날짜 폴더에 group_id.json 형태로 저장
        today_date_str = datetime.now().strftime("%Y-%m-%d")
        group_dir = os.path.join(GROUPED_DATA_DIR, today_date_str) # data/processed/grouped_articles/YYYY-MM-DD/
        
        output_filename = f"{group_id}.json"
        # filepath = get_output_path(GROUPED_DATA_DIR, "grouped", group_id, output_filename)
        # 위처럼 get_output_path를 사용하려면 site_name, category_name 인자 핸들링이 필요.
        # 여기서는 직접 경로 조합:
        if not os.path.exists(group_dir):
            os.makedirs(group_dir)
        filepath = os.path.join(group_dir, output_filename)

        save_tasks.append(save_json_async(group_data, filepath))
        saved_group_count += 1

    await asyncio.gather(*save_tasks)
    print(f"총 {saved_group_count}개의 그룹화된 기사 묶음을 저장했습니다.")
    print("===== 기사 그룹핑 프로세스 완료 =====")

if __name__ == '__main__':
    asyncio.run(main()) 