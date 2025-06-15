import pandas as pd
from pytrends.request import TrendReq
import matplotlib.pyplot as plt
import time

keywords = ['이재명', '김문수', '이준석', '권영국']

period = 'today 5-y'
trend_df = None

# API 요청 제한에 대응하기 위한 재시도 로직
for attempt in range(3):  # 총 3번 시도
    try:
        print(f"Google Trends 데이터 요청 중... (시도 {attempt + 1}/3)")
        # 요청 제한을 피하기 위해 요청 사이에 지연 시간을 줍니다.
        time.sleep(attempt * 5)
        
        trend_obj = TrendReq(hl='ko-KR', tz=540, timeout=(10, 25), retries=2, backoff_factor=0.5)
        trend_obj.build_payload(kw_list=keywords, timeframe=period, geo='KR')
        trend_df = trend_obj.interest_over_time()
        
        if trend_df is not None and not trend_df.empty:
            print("데이터 수집 성공!")
            break  # 성공 시 루프 탈출
            
    except Exception as e:
        if '429' in str(e) or 'Too Many Requests' in str(e):
            wait_time = (attempt + 1) * 10
            print(f"API 요청 제한(429) 감지. {wait_time}초 후 재시도합니다.")
            time.sleep(wait_time)
        else:
            print(f"오류 발생: {e}")
            break  # 다른 종류의 오류는 재시도하지 않음

if trend_df is None or trend_df.empty:
    print("데이터를 가져오는 데 최종적으로 실패했습니다. 스크립트를 종료합니다.")
else:
    colors = ['blue', 'red', 'orange', 'yellow']

    plt.rc('font', family='NanumGothic')
    plt.style.use('ggplot')
    plt.figure(figsize=(14, 5), dpi=100)

    for keyword, color in zip(keywords, colors):
        trend_df[keyword].plot(label=keyword, color=color)

    # '제 20대 대선' 수직선 추가
    event_date = pd.to_datetime('2022-03-09')
    plt.axvline(x=event_date, color='black', linestyle='--', linewidth=1)
    plt.text(event_date + pd.Timedelta(days=7), plt.ylim()[1]*0.95,
             '제 20대 대선', rotation=90, verticalalignment='top', fontsize=10)

    plt.title('장기간 대선 후보 <구글> 검색 트렌드', fontsize=15)
    plt.xlabel('')
    plt.ylabel('검색 비율 (비교 기준 100)')
    plt.grid(True)
    plt.legend(loc='best', title='후보자')
    plt.tight_layout()
    plt.show()