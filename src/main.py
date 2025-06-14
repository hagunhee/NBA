#!/usr/bin/env python3
"""
네이버 블로그 자동화 프로그램
메인 진입점
"""
import sys
import os
import logging
import signal
from pathlib import Path
from typing import Optional
import argparse
import threading
import time

# 프로젝트 경로 설정
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_path))

# 환경 변수 로드
from dotenv import load_dotenv

load_dotenv()


def setup_signal_handlers():
    """시그널 핸들러 설정 (Ctrl+C 처리)"""

    def signal_handler(signum, frame):
        print("\n프로그램 종료 중...")
        # GUI가 있다면 안전하게 종료
        try:
            import tkinter as tk

            for widget in tk._default_root.winfo_children() if tk._default_root else []:
                if hasattr(widget, "quit"):
                    widget.quit()
        except:
            pass

        os._exit(0)  # 강제 종료

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)


def check_requirements() -> bool:
    """필수 요구사항 확인"""
    errors = []

    # Python 버전 확인
    if sys.version_info < (3, 8):
        errors.append("Python 3.8 이상이 필요합니다.")

    # 필수 모듈 확인
    required_modules = [
        "selenium",
        "undetected_chromedriver",
        "cryptography",
        "requests",
        "psutil",
        "tkinter",
    ]

    for module in required_modules:
        try:
            if module == "tkinter":
                import tkinter
            else:
                __import__(module)
        except ImportError:
            errors.append(f"{module} 모듈이 설치되지 않았습니다.")

    # Firebase는 선택적
    try:
        import firebase_admin
    except ImportError:
        print("경고: firebase_admin이 설치되지 않았습니다. 라이선스 기능이 제한됩니다.")

    # 에러가 있으면 출력
    if errors:
        print("=== 요구사항 확인 실패 ===")
        for error in errors:
            print(f"✗ {error}")
        print("\n다음 명령어로 필수 패키지를 설치하세요:")
        print("pip install -r requirements.txt")
        return False

    return True


def setup_environment():
    """환경 설정"""
    # 로그 디렉토리 생성
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # 캐시 디렉토리 생성
    cache_dir = project_root / "cache"
    cache_dir.mkdir(exist_ok=True)

    # 데이터 디렉토리 생성
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)


def parse_arguments():
    """명령행 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="네이버 블로그 자동화 프로그램",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py                  # 일반 GUI 모드
  python main.py --admin          # 관리자 모드
  python main.py --headless       # 헤드리스 모드
  python main.py --debug          # 디버그 모드
  python main.py --profile work   # 특정 프로필로 시작
        """,
    )

    parser.add_argument("--admin", action="store_true", help="관리자 모드로 실행")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="헤드리스 모드로 실행 (브라우저 창 숨김)",
    )
    parser.add_argument(
        "--debug", action="store_true", help="디버그 모드 (상세 로그 출력)"
    )
    parser.add_argument("--profile", type=str, help="시작할 프로필 이름")
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="설정 파일 경로 (기본값: config.json)",
    )
    parser.add_argument(
        "--no-update-check", action="store_true", help="자동 업데이트 확인 비활성화"
    )
    parser.add_argument(
        "--safe-mode", action="store_true", help="안전 모드 (라이선스 검증 건너뛰기)"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 2.0.0")

    return parser.parse_args()


def run_admin_mode():
    """관리자 모드 실행"""
    print("=== 관리자 모드 ===")

    try:
        from core.admin import AdminMenu

        admin = AdminMenu()
        admin.run()
    except Exception as e:
        print(f"관리자 모드 실행 실패: {e}")
        import traceback

        traceback.print_exc()


def init_gui_safely(args) -> Optional[object]:
    """GUI 안전 초기화"""
    print("GUI 초기화 중...")

    try:
        # 단계별 초기화 확인
        print("1. 모듈 임포트 시작...")

        # 각 컴포넌트를 개별적으로 임포트하여 문제 파악
        try:
            from core.config import Config

            print("  - Config 임포트 성공")
        except Exception as e:
            print(f"  - Config 임포트 실패: {e}")

        try:
            from core.security import SecurityManager

            print("  - SecurityManager 임포트 성공")
        except Exception as e:
            print(f"  - SecurityManager 임포트 실패: {e}")

        try:
            from core.license_manager import LicenseManager

            print("  - LicenseManager 임포트 성공")
        except Exception as e:
            print(f"  - LicenseManager 임포트 실패: {e}")

        try:
            from gui.main_window_v2 import MainApplication

            print("  - MainApplication 임포트 성공")
        except Exception as e:
            print(f"  - MainApplication 임포트 실패: {e}")
            raise

        print("2. MainApplication 인스턴스 생성...")
        app = MainApplication()
        print("3. GUI 초기화 완료")
        return app

    except Exception as e:
        print(f"GUI 초기화 중 예외: {e}")
        import traceback

        traceback.print_exc()
        return None


def run_gui_mode(args):
    """GUI 모드 실행"""
    print("네이버 블로그 자동화 프로그램 시작...")

    try:
        # 안전한 GUI 초기화
        app = init_gui_safely(args)

        if not app:
            print("GUI 초기화에 실패했습니다.")
            print("다음을 확인해주세요:")
            print("1. 모든 필수 모듈이 설치되어 있는지")
            print("2. 디스플레이 환경이 올바른지")
            print("3. 관리자 권한이 필요한지")
            return

        # 명령행 옵션 적용
        if args.headless and hasattr(app, "toolbar"):
            app.toolbar.headless_var.set(True)

        if args.profile and hasattr(app, "toolbar"):
            app.toolbar.profile_var.set(args.profile)

        # 업데이트 확인 (백그라운드)
        if not args.no_update_check:

            def check_updates():
                try:
                    time.sleep(2)  # GUI 로드 후 체크
                    # 업데이트 확인 로직
                    pass
                except:
                    pass

            threading.Thread(target=check_updates, daemon=True).start()

        print("GUI 실행 중...")

        # 안전한 실행
        try:
            app.run()
        except KeyboardInterrupt:
            print("\n사용자가 프로그램을 중단했습니다.")
        except Exception as e:
            print(f"GUI 실행 중 오류: {e}")
            import traceback

            traceback.print_exc()

    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {e}")
        import traceback

        traceback.print_exc()

        # GUI 오류 대화상자 표시 시도
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "실행 오류", f"프로그램 실행 중 오류가 발생했습니다.\n\n{str(e)}"
            )
            root.destroy()
        except:
            pass


def main():
    """메인 함수"""
    # 시그널 핸들러 설정
    setup_signal_handlers()

    # 인자 파싱
    args = parse_arguments()

    # 로깅 설정
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)

    # 환경 설정
    setup_environment()

    print("시스템 확인 중...")

    # 요구사항 확인
    if not check_requirements():
        input("Press Enter to exit...")
        sys.exit(1)

    # API 키 확인
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("경고: ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        print("AI 기반 댓글 생성 기능이 제한될 수 있습니다.")

    print("시스템 확인 완료!")

    # 실행 모드 선택
    if args.admin:
        run_admin_mode()
    else:
        run_gui_mode(args)


def setup_logging(level=logging.INFO):
    """로깅 설정"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # 파일 핸들러
    from datetime import datetime

    log_file = project_root / "logs" / f"app_{datetime.now().strftime('%Y%m%d')}.log"

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(log_format))
    except:
        file_handler = None
        print("로그 파일 생성 실패, 콘솔만 사용합니다.")

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    if file_handler:
        root_logger.addHandler(file_handler)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("firebase_admin").setLevel(logging.WARNING)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
        os._exit(0)
    except Exception as e:
        print(f"\n예상치 못한 오류가 발생했습니다: {e}")
        import traceback

        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)
