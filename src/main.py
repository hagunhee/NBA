#!/usr/bin/env python3
"""
네이버 블로그 자동 이웃관리 프로그램
메인 진입점
"""
import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

from gui.main_window import BlogManagerApp
from core.admin import AdminMenu
import argparse


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="네이버 블로그 자동 이웃관리")
    parser.add_argument("--admin", action="store_true", help="관리자 모드")
    args = parser.parse_args()

    # Claude API 키 설정 (환경 변수 또는 .env 파일에서 로드)
    if not os.getenv("ANTHROPIC_API_KEY"):
        # 개발자가 여기에 API 키를 설정하거나 .env 파일 사용
        print("경고: ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    if args.admin:
        # 관리자 모드
        admin = AdminMenu()
        admin.run()
    else:
        # 일반 사용자 모드
        app = BlogManagerApp()
        app.run()


if __name__ == "__main__":
    main()
