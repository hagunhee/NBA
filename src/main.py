#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import argparse
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.gui.main_window import MainWindow
from src.core.config import Config
from src.utils.logger import Logger


def check_requirements():
    """필수 파일/디렉토리 확인"""
    required_dirs = ["logs", "cache", "resources/icons", "resources/config"]

    for dir_path in required_dirs:
        os.makedirs(dir_path, exist_ok=True)

    # .env 파일 확인
    if not os.path.exists(".env"):
        print("경고: .env 파일이 없습니다. .env.example을 복사하여 설정해주세요.")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="네이버 블로그 자동 이웃관리 프로그램")
    parser.add_argument("--debug", action="store_true", help="디버그 모드")
    parser.add_argument(
        "--config", type=str, default="config.json", help="설정 파일 경로"
    )

    args = parser.parse_args()

    # 환경 체크
    check_requirements()

    # 로거 초기화
    logger = Logger()
    logger.info("프로그램 시작")

    try:
        # GUI 실행
        app = MainWindow()
        app.run()
    except Exception as e:
        logger.error("프로그램 실행 오류", e)
        print(f"오류 발생: {e}")
        sys.exit(1)
    finally:
        logger.info("프로그램 종료")


if __name__ == "__main__":
    main()
