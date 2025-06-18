import logging
import sys

DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_LOG_LEVEL = logging.INFO

def setup_logger(name="default_logger", level=DEFAULT_LOG_LEVEL, log_format=DEFAULT_LOG_FORMAT):
    """
    기본 로거를 설정합니다.
    콘솔 핸들러를 기본으로 추가합니다.
    """
    logger = logging.getLogger(name)
    if not logger.handlers: # 핸들러가 이미 설정되어 있는지 확인 (중복 추가 방지)
        logger.setLevel(level)

        # 콘솔 핸들러 설정
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)

        # 포매터 설정
        formatter = logging.Formatter(log_format)
        ch.setFormatter(formatter)

        # 핸들러를 로거에 추가
        logger.addHandler(ch)
    
    return logger

# 예시: 기본 로거 생성
# logger = setup_logger(__name__)
# logger.info("Logger setup complete.") 