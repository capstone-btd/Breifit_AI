from .base_collector import BaseCollector
from .cnn_collector import CnnCollector
# from .ap_collector import APCollector # AP Collector 임포트 제거
from .bbc_collector import BBCCollector # bbc_collector.py의 클래스 이름과 일치시킴
# from .nyt_collector import NytCollector # API 키 필요로 주석 처리
# from .reuters_collector import ReutersCollector
from .guardian_collector import GuardianCollector
# from "deprecated/npr_collector" import NprCollector
from .thetimes_collector import TheTimesCollector # TheTimesCollector 임포트 추가
from .yonhap_collector import YonhapCollector
from .chosun_collector import ChosunCollector
from .joongang_collector import JoongangCollector
from .donga_collector import DongaCollector
from .hankyoreh_collector import HankyorehCollector
from .kyunghyang_collector import KyunghyangCollector

# 사용 가능한 모든 컬렉터 클래스를 매핑합니다.
# 키는 사이트 이름(configs/news_sites.yaml 등에서 사용될 식별자), 값은 컬렉터 클래스입니다.
COLLECTOR_CLASSES = {
    "cnn": CnnCollector,
    # "ap": APCollector, # AP Collector 제거 - 이후 forbidden 해결되면 사용
    "bbc": BBCCollector, # bbc_collector.py의 클래스 이름과 일치시킴
    # "nyt": NytCollector, 
    # "reuters": ReutersCollector,
    "the_guardian": GuardianCollector,
    # "npr": NprCollector,
    "the_times": TheTimesCollector, # TheTimesCollector 추가
    "연합": YonhapCollector,
    "조선": ChosunCollector,
    "중앙": JoongangCollector,
    "동아": DongaCollector,
    "한겨레": HankyorehCollector,
    "경향": KyunghyangCollector,
}

def get_collector_class(name):
    klass = COLLECTOR_CLASSES.get(name.lower())
    if klass is None:
        raise ValueError(f"Unsupported collector: {name}. Supported collectors are: {list(COLLECTOR_CLASSES.keys())}")
    return klass 