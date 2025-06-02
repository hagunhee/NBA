import logging
import os
from datetime import datetime
from typing import Optional


class Logger:
    """로깅 시스템"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # 로그 파일명
        log_filename = f"blog_manager_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = os.path.join(log_dir, log_filename)

        # 로거 설정
        self.logger = logging.getLogger("NaverBlogManager")
        self.logger.setLevel(logging.DEBUG)

        # 파일 핸들러
        file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # 포맷터
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)

        # 핸들러 추가
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)

    def log(self, message: str, level: str = "INFO"):
        """로그 기록"""
        level = level.upper()
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)

    def debug(self, message: str):
        """디버그 로그"""
        self.logger.debug(message)

    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)

    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)

    def error(self, message: str, exception: Optional[Exception] = None):
        """에러 로그"""
        if exception:
            self.logger.error(f"{message}: {str(exception)}", exc_info=True)
        else:
            self.logger.error(message)
