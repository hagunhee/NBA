"""
logger.py

통합 로깅 설정 모듈
사용법:
    from logger import Logger, get_logger
    # 클래스 사용
    logger = Logger(
        name="NaverBlogManager",
        log_dir="logs",
        level=logging.DEBUG,
        max_bytes=10*1024*1024,
        backup_count=5
    )
    logger.info("애플리케이션 시작")

    # 혹은 간편 함수 사용
    logger = get_logger(
        name="NaverBlogManager",
        log_dir="logs",
        level=logging.DEBUG
    )
    logger.error("에러 발생")
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class Logger:
    """로깅 시스템 클래스"""

    def __init__(
        self,
        name: str = "app",
        log_dir: str = "logs",
        level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        # 로깅 이름 및 레벨 설정
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 로그 디렉터리 생성
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        # 로그 파일 경로 (/logs/name_YYYYMMDD.log)
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{name}_{date_str}.log"
        file_path = Path(log_dir) / filename

        # 로테이팅 파일 핸들러
        file_handler = RotatingFileHandler(
            filename=str(file_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        # 스트림 핸들러 (콘솔 출력)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)

        # 포맷터 설정
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # 핸들러 중복 추가 방지
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(stream_handler)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, exception: Optional[Exception] = None, **kwargs):
        if exception:
            self.logger.error(f"{msg} : {exception}", exc_info=True, *args, **kwargs)
        else:
            self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def log(self, level: int, msg: str, *args, **kwargs):
        """범용 로그 메서드"""
        self.logger.log(level, msg, *args, **kwargs)


def get_logger(
    name: str = "app",
    log_dir: str = "logs",
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Logger 인스턴스를 생성하고 내부 logger 객체를 반환합니다.
    :param name: 로그 이름
    :param log_dir: 로그 저장 디렉터리
    :param level: 로깅 레벨
    :param max_bytes: 파일 로테이션 최대 바이트
    :param backup_count: 보관할 백업 파일 개수
    """
    return Logger(
        name=name,
        log_dir=log_dir,
        level=level,
        max_bytes=max_bytes,
        backup_count=backup_count,
    ).logger
