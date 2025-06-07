"""
네이버 블로그 자동화 모듈 (naver_automation.py)

- 브라우저 종료 방지
- 디버깅 로그 강화
- BrowserMonitor 통합
- 스텔스 모드 강화 및 인간 행동 시뮬레이션 기능 포함
"""

import os
import time
import random
import threading
import psutil
import signal
from datetime import datetime
from typing import Dict, Tuple, List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchWindowException,
    InvalidSessionIdException,
)

import undetected_chromedriver as uc
from dotenv import load_dotenv


class BrowserMonitor:
    """브라우저 상태 실시간 모니터링 클래스"""

    def __init__(self, automation_instance):
        self.automation = automation_instance
        self.monitoring = False
        self.monitor_thread = None
        self.browser_crashes: List[Dict] = []
        self.system_alerts: List[Dict] = []

    def start_monitoring(self):
        """모니터링 시작"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(
                target=self._monitor_loop, daemon=True
            )
            self.monitor_thread.start()
            print("🔍 브라우저 모니터링 시작됨")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("🔍 브라우저 모니터링 중지됨")

    def _monitor_loop(self):
        """모니터링 메인 루프"""
        last_check = time.time()
        consecutive_failures = 0

        while self.monitoring:
            try:
                current_time = time.time()

                # 5초마다 체크
                if current_time - last_check >= 5:
                    if (
                        self.automation
                        and hasattr(self.automation, "driver")
                        and self.automation.driver
                    ):

                        # 브라우저 상태 확인
                        browser_alive = self._check_browser_health()

                        if not browser_alive:
                            consecutive_failures += 1
                            timestamp = datetime.now().strftime("%H:%M:%S")

                            crash_info = {
                                "timestamp": timestamp,
                                "consecutive_failures": consecutive_failures,
                                "system_memory": psutil.virtual_memory().percent,
                                "system_cpu": psutil.cpu_percent(),
                            }

                            self.browser_crashes.append(crash_info)

                            print(f"🚨 [{timestamp}] 브라우저 상태 이상 감지!")
                            print(f"   연속 실패: {consecutive_failures}회")
                            print(
                                f"   시스템 메모리: {crash_info['system_memory']:.1f}%"
                            )
                            print(f"   시스템 CPU: {crash_info['system_cpu']:.1f}%")

                            # 연속 3회 실패 시 자세한 분석
                            if consecutive_failures >= 3:
                                self._analyze_crash_cause()
                                consecutive_failures = 0  # 리셋
                        else:
                            consecutive_failures = 0

                        # 시스템 리소스 체크
                        self._check_system_resources()

                    last_check = current_time

                time.sleep(1)

            except Exception as e:
                print(f"모니터링 루프 오류: {e}")
                time.sleep(5)

    def _check_browser_health(self) -> bool:
        """브라우저 건강상태 확인"""
        try:
            if not self.automation.driver:
                return False

            tests = [
                lambda: self.automation.driver.current_url,
                lambda: self.automation.driver.title,
                lambda: self.automation.driver.execute_script("return true"),
            ]

            failed = 0
            for test in tests:
                try:
                    test()
                except:
                    failed += 1

            # 절반 이상 성공하면 OK
            return failed < len(tests) / 2

        except Exception:
            return False

    def _check_system_resources(self):
        """시스템 리소스 확인"""
        try:
            memory = psutil.virtual_memory()
            cpu = psutil.cpu_percent()

            # 메모리 부족 경고
            if memory.percent > 90:
                alert = f"⚠️ 메모리 부족: {memory.percent:.1f}%"
                if alert not in [a["message"] for a in self.system_alerts[-5:]]:
                    self.system_alerts.append(
                        {
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "type": "memory",
                            "message": alert,
                        }
                    )
                    print(alert)

            # CPU 과부하 경고
            if cpu > 95:
                alert = f"⚠️ CPU 과부하: {cpu:.1f}%"
                if alert not in [a["message"] for a in self.system_alerts[-5:]]:
                    self.system_alerts.append(
                        {
                            "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "type": "cpu",
                            "message": alert,
                        }
                    )
                    print(alert)

        except Exception as e:
            print(f"시스템 리소스 확인 오류: {e}")

    def _analyze_crash_cause(self):
        """크래시 원인 분석"""
        print("\n🔍 브라우저 크래시 원인 분석 중...")

        try:
            # Chrome 프로세스 상태 확인
            chrome_processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "status", "memory_percent", "cpu_percent"]
            ):
                try:
                    if "chrome" in proc.info["name"].lower():
                        chrome_processes.append(
                            {
                                "pid": proc.info["pid"],
                                "status": proc.info["status"],
                                "memory": proc.info["memory_percent"],
                                "cpu": proc.info["cpu_percent"],
                            }
                        )
                except:
                    pass

            print(f"Chrome 프로세스 수: {len(chrome_processes)}")
            for proc in chrome_processes:
                print(
                    f"  PID {proc['pid']}: {proc['status']}, 메모리 {proc['memory']:.1f}%, CPU {proc['cpu']:.1f}%"
                )

            # 네이버 보안 정책에 의한 종료 가능성 체크
            if hasattr(self.automation, "last_known_url"):
                url = self.automation.last_known_url
                if "naver.com" in url:
                    print("⚠️ 네이버 사이트에서 크래시 - 보안 정책에 의한 종료 가능성")
                    print("   해결방안:")
                    print("   1. User-Agent 변경")
                    print("   2. 더 자연스러운 인터벌 적용")
                    print("   3. 탐지 회피 스크립트 강화")

            # 메모리 부족 체크
            memory = psutil.virtual_memory()
            if memory.percent > 85:
                print(f"⚠️ 메모리 부족 가능성: {memory.percent:.1f}%")
                print("   해결방안: 브라우저 재시작 권장")

            # 최근 크래시 패턴 분석
            if len(self.browser_crashes) >= 3:
                recent_crashes = self.browser_crashes[-3:]
                intervals = []
                for i in range(1, len(recent_crashes)):
                    prev_time = datetime.strptime(
                        recent_crashes[i - 1]["timestamp"], "%H:%M:%S"
                    )
                    curr_time = datetime.strptime(
                        recent_crashes[i]["timestamp"], "%H:%M:%S"
                    )
                    intervals.append((curr_time - prev_time).total_seconds())

                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    print(f"평균 크래시 간격: {avg_interval:.1f}초")
                    if avg_interval < 60:
                        print("⚠️ 크래시가 너무 빈번함 - 자동화 일시 중단 권장")

        except Exception as e:
            print(f"크래시 분석 중 오류: {e}")

        print("🔍 크래시 원인 분석 완료\n")

    def get_summary(self) -> Dict:
        """모니터링 요약 반환"""
        return {
            "crashes": len(self.browser_crashes),
            "system_alerts": len(self.system_alerts),
            "last_crash": self.browser_crashes[-1] if self.browser_crashes else None,
            "monitoring": self.monitoring,
        }


def enhance_stealth_mode(driver) -> bool:
    """네이버 보안 탐지 회피 강화"""
    try:
        print("🥷 스텔스 모드 강화 중...")

        stealth_script = """
        // WebDriver 탐지 제거
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

        // Chrome 자동화 탐지 제거
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });

        // 언어 설정 자연스럽게
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ko-KR', 'ko', 'en-US', 'en']
        });

        // 화면 크기 자연스럽게
        Object.defineProperty(screen, 'width', {get: () => 1920});
        Object.defineProperty(screen, 'height', {get: () => 1080});

        // 권한 상태 자연스럽게
        const getParameter = WebGLRenderingContext.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter(parameter);
        };

        // 마우스 이벤트 시뮬레이션
        setInterval(() => {
            const event = new MouseEvent('mousemove', {
                clientX: Math.random() * window.innerWidth,
                clientY: Math.random() * window.innerHeight
            });
            document.dispatchEvent(event);
        }, 30000 + Math.random() * 60000); // 30-90초마다

        // 스크롤 이벤트 시뮬레이션
        setInterval(() => {
            window.scrollBy(0, Math.random() * 100 - 50);
        }, 45000 + Math.random() * 30000); // 45-75초마다

        console.log('🥷 스텔스 모드 활성화 완료');
        """

        driver.execute_script(stealth_script)
        print("✓ 스텔스 모드 강화 완료")
        return True

    except Exception as e:
        print(f"✗ 스텔스 모드 강화 실패: {e}")
        return False


def simulate_human_behavior(driver):
    """인간다운 브라우저 동작 시뮬레이션"""
    try:
        # 무작위 마우스 움직임
        driver.execute_script(
            f"""
            const event = new MouseEvent('mousemove', {{
                clientX: {random.randint(100, 800)},
                clientY: {random.randint(100, 600)}
            }});
            document.dispatchEvent(event);
            """
        )

        # 무작위 키보드 이벤트 (Ctrl 키 등)
        if random.random() < 0.1:  # 10% 확률
            driver.execute_script(
                """
                const event = new KeyboardEvent('keydown', {
                    key: 'Control',
                    ctrlKey: true
                });
                document.dispatchEvent(event);

                setTimeout(() => {
                    const upEvent = new KeyboardEvent('keyup', {
                        key: 'Control'
                    });
                    document.dispatchEvent(upEvent);
                }, 100);
                """
            )

        # 페이지 일부 영역 클릭 (빈 공간)
        if random.random() < 0.05:  # 5% 확률
            driver.execute_script(
                f"""
                const x = {random.randint(50, 200)};
                const y = {random.randint(50, 200)};
                const element = document.elementFromPoint(x, y);
                if (element && element.tagName !== 'A' && element.tagName !== 'BUTTON') {{
                    element.click();
                }}
                """
            )

    except Exception as e:
        print(f"인간 동작 시뮬레이션 오류: {e}")


class NaverBlogAutomation:
    """네이버 블로그 자동화 클래스"""

    def __init__(self, headless: bool = False):
        self.driver = None
        self.wait = None
        self.headless = headless
        self.is_logged_in = False
        self.is_running = False
        self.browser_pid: Optional[int] = None
        self.last_known_url = ""

        # 브라우저 생존 모니터링
        self.browser_alive_check_count = 0

        # 모니터링 인스턴스
        self.browser_monitor: Optional[BrowserMonitor] = None

        print(f"\n=== NaverBlogAutomation 초기화 (헤드리스: {headless}) ===")

        # === .env 파일 로드 및 API 키 확인 ===
        print("\n=== .env 파일 및 Claude API 설정 확인 ===")
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        print(f".env 파일 경로: {env_path}")
        print(f".env 파일 존재: {os.path.exists(env_path)}")

        load_result = load_dotenv(env_path)
        print(f".env 파일 로드 결과: {load_result}")

        env_api_key = os.getenv("ANTHROPIC_API_KEY")
        if env_api_key:
            print(f"환경변수에서 읽은 API 키: {env_api_key[:20]}...")
        else:
            print("환경변수 API 키: 없음")

        # (이후 Claude API 초기화 로직은 이전 내용과 동일하므로 생략)

    def init_browser(self) -> bool:
        """브라우저 초기화 - 종료 방지 및 모니터링 통합"""
        try:
            print("브라우저 초기화 시작...")
            print(f"헤드리스 모드: {self.headless}")

            # undetected-chromedriver 설정
            try:
                chrome_options = uc.ChromeOptions()

                if not self.headless:
                    print("일반 모드 - 브라우저 창 유지 설정")
                    chrome_options.add_argument("--no-first-run")
                    chrome_options.add_argument("--no-default-browser-check")
                    chrome_options.add_argument("--disable-default-apps")
                    chrome_options.add_argument("--disable-background-timer-throttling")
                    chrome_options.add_argument(
                        "--disable-backgrounding-occluded-windows"
                    )
                    chrome_options.add_argument("--disable-renderer-backgrounding")
                    chrome_options.add_argument("--keep-alive-for-test")
                else:
                    print("헤드리스 모드 설정")
                    chrome_options.add_argument("--headless")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")

                # 공통 옵션
                chrome_options.add_argument("--window-size=1920,1080")
                chrome_options.add_argument(
                    "--disable-blink-features=AutomationControlled"
                )
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument(
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                chrome_options.add_experimental_option(
                    "excludeSwitches", ["enable-automation"]
                )
                chrome_options.add_experimental_option("useAutomationExtension", False)

                prefs = {
                    "profile.default_content_setting_values": {
                        "notifications": 2,
                        "popups": 2,
                    },
                    "profile.managed_default_content_settings": {"images": 2},
                }
                chrome_options.add_experimental_option("prefs", prefs)

                self.driver = uc.Chrome(options=chrome_options, version_main=None)
                print("간단한 undetected-chromedriver 성공!")

                # 브라우저 PID 저장
                try:
                    self.browser_pid = self.driver.service.process.pid
                    print(f"브라우저 프로세스 ID: {self.browser_pid}")
                except:
                    print("브라우저 프로세스 ID 확인 실패")

            except Exception as e:
                print(f"브라우저 초기화 실패: {e}")
                return False

            # 탐지 회피 스크립트
            try:
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                print("기본 탐지 회피 스크립트 적용 완료")

                self.driver.execute_script(
                    """
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['ko-KR', 'ko', 'en-US', 'en']
                    });
                    window.addEventListener('beforeunload', function(e) {
                        console.log('브라우저 종료 시도 감지됨');
                        return '정말 종료하시겠습니까?';
                    });
                    """
                )
                print("고급 탐지 회피 및 종료 방지 스크립트 적용 완료")

            except Exception as e:
                print(f"탐지 회피 스크립트 적용 실패: {e}")

            # WebDriverWait 객체 생성
            self.wait = WebDriverWait(self.driver, 15)

            # 브라우저 테스트 (구글 → 네이버)
            try:
                print("브라우저 기본 테스트 중...")
                self.driver.get("https://www.google.com")
                self.last_known_url = self.driver.current_url
                print(f"구글 접속 성공: {self.last_known_url}")

                self.driver.get("https://www.naver.com")
                self.last_known_url = self.driver.current_url
                print(f"네이버 접속 성공: {self.last_known_url}")

            except Exception as e:
                print(f"브라우저 테스트 실패: {e}")
                return False

            self.is_running = True
            print(
                f"✓ 브라우저 초기화 최종 성공! (헤드리스: {'ON' if self.headless else 'OFF'})"
            )

            # 브라우저 모니터링 시작
            self.browser_monitor = BrowserMonitor(self)
            self.browser_monitor.start_monitoring()

            # 초기 브라우저 상태 기록
            self.log_browser_status("초기화 완료")

            return True

        except Exception as e:
            print(f"브라우저 초기화 완전 실패: {e}")
            return False

    def log_browser_status(self, operation: str = "상태 확인") -> bool:
        """브라우저 상태 상세 로깅"""
        try:
            print(f"\n=== 브라우저 상태 확인: {operation} ===")

            # 현재 URL
            try:
                current_url = self.driver.current_url
                print(f"✓ 현재 URL: {current_url}")
                self.last_known_url = current_url
            except Exception as e:
                print(f"✗ URL 확인 실패: {e}")
                return False

            # Document readyState
            try:
                ready_state = self.driver.execute_script("return document.readyState")
                print(f"✓ Document Ready State: {ready_state}")
            except Exception as e:
                print(f"✗ JavaScript 실행 실패: {e}")
                return False

            # 윈도우 핸들 수
            try:
                handles = self.driver.window_handles
                print(f"✓ 윈도우 핸들 수: {len(handles)}")
            except Exception as e:
                print(f"✗ 윈도우 핸들 확인 실패: {e}")
                return False

            # 브라우저 프로세스 상태
            if self.browser_pid:
                try:
                    process = psutil.Process(self.browser_pid)
                    print(f"✓ 브라우저 프로세스 상태: {process.status()}")
                    print(
                        f"✓ 브라우저 메모리 사용량: {process.memory_info().rss / 1024 / 1024:.1f} MB"
                    )
                except Exception as e:
                    print(f"✗ 브라우저 프로세스 확인 실패: {e}")

            # 전체 Chrome 프로세스 수
            chrome_processes = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    if "chrome" in proc.info["name"].lower():
                        chrome_processes.append(proc.info["pid"])
                except:
                    pass
            print(f"✓ 실행 중인 Chrome 프로세스: {len(chrome_processes)}개")

            print(f"=== 브라우저 상태 확인 완료 ===\n")
            return True

        except Exception as e:
            print(f"✗ 브라우저 상태 확인 중 오류: {e}")
            return False

    def check_browser_alive(self) -> bool:
        """브라우저 생존 여부 확인 (간단 체크)"""
        try:
            self.browser_alive_check_count += 1

            tests = [
                ("URL 접근", lambda: self.driver.current_url),
                ("JavaScript 실행", lambda: self.driver.execute_script("return true")),
                ("Title 확인", lambda: self.driver.title),
                ("Window 핸들", lambda: len(self.driver.window_handles) > 0),
            ]

            failed_tests = []
            for test_name, test_func in tests:
                try:
                    test_func()
                except Exception as e:
                    failed_tests.append(f"{test_name}: {e}")

            if failed_tests:
                print(
                    f"\n⚠️ 브라우저 상태 검사 실패 (체크 #{self.browser_alive_check_count}):"
                )
                for failure in failed_tests:
                    print(f"  ✗ {failure}")

                # 프로세스 레벨 확인
                if self.browser_pid:
                    try:
                        process = psutil.Process(self.browser_pid)
                        print(f"  브라우저 프로세스 상태: {process.status()}")
                    except psutil.NoSuchProcess:
                        print(f"  ⚠️ 브라우저 프로세스 {self.browser_pid}가 종료됨!")
                        return False
                    except Exception as e:
                        print(f"  프로세스 확인 오류: {e}")

                return len(failed_tests) < len(tests) / 2

            return True

        except Exception as e:
            print(f"✗ 브라우저 생존 확인 중 오류: {e}")
            return False

    def prevent_browser_close(self):
        """브라우저 종료 방지 스크립트 실행"""
        try:
            print("브라우저 종료 방지 스크립트 실행...")

            prevention_script = """
            // 브라우저 종료 방지
            window.addEventListener('beforeunload', function(e) {
                console.log('브라우저 종료 시도 감지 - 방지 중...');
                e.preventDefault();
                e.returnValue = '';
                return '';
            });

            // 페이지 이탈 방지
            window.addEventListener('unload', function(e) {
                console.log('페이지 이탈 감지 - 방지 중...');
                e.preventDefault();
            });
            console.log('브라우저 종료 방지 스크립트 활성화됨');
            """

            self.driver.execute_script(prevention_script)
            print("✓ 브라우저 종료 방지 스크립트 활성화 완료")

        except Exception as e:
            print(f"✗ 브라우저 종료 방지 스크립트 실행 실패: {e}")

    def monitor_browser_during_operation(self, operation_name: str) -> bool:
        """작업 중 브라우저 모니터링 (간이체크 + 시스템 정보 출력)"""
        try:
            if not self.check_browser_alive():
                print(f"🚨 {operation_name} 중 브라우저 종료 감지!")

                # 종료 원인 간단 분석
                print("브라우저 종료 원인 분석 중...")
                memory = psutil.virtual_memory()
                print(f"시스템 메모리 사용률: {memory.percent}%")

                # Chrome 프로세스 확인
                chrome_procs = []
                for proc in psutil.process_iter(["pid", "name", "status"]):
                    try:
                        if "chrome" in proc.info["name"].lower():
                            chrome_procs.append(
                                f"PID {proc.info['pid']}: {proc.info['status']}"
                            )
                    except:
                        pass

                print(f"Chrome 프로세스 상태: {chrome_procs}")
                return False

            return True

        except Exception as e:
            print(f"브라우저 모니터링 중 오류: {e}")
            return False

    def process_post(self, post_info: Dict, settings: Dict) -> Tuple[bool, str]:
        """포스트 처리 - 브라우저 종료 방지 및 모니터링 통합"""
        try:
            print(f"\n{'='*60}")
            print(f"포스트 처리 시작: {post_info.get('title', '')[:50]}...")
            print(f"{'='*60}")

            # 작업 전 브라우저 상태 확인
            if not self.check_browser_alive():
                return False, "브라우저가 응답하지 않습니다"

            # 종료 방지 스크립트 재적용
            self.prevent_browser_close()

            # 1. 포스트 방문
            print(f"1. 포스트 방문 중...")
            self.driver.get(post_info["url"])

            # 페이지 로드 후 모니터링
            if not self.monitor_browser_during_operation("페이지 로드"):
                return False, "페이지 로드 중 브라우저 종료됨"

            time.sleep(random.uniform(3, 5))

            # 2. 포스트 정보 수집
            print(f"2. 포스트 정보 수집 중...")

            # 수집 전 모니터링
            if not self.monitor_browser_during_operation("정보 수집 전"):
                return False, "정보 수집 전 브라우저 종료됨"

            post_content = self.collect_post_info()

            # 수집 후 모니터링
            if not self.monitor_browser_during_operation("정보 수집 후"):
                return False, "정보 수집 후 브라우저 종료됨"

            if not post_content:
                return False, "포스트 정보를 수집할 수 없습니다"

            # === 수집된 본문 출력 ===
            print(f"\n{'='*60}")
            print(f"📄 수집된 포스트 정보:")
            print(f"제목: {post_content.get('title', 'N/A')}")
            print(f"본문 길이: {len(post_content.get('content', ''))}자")
            print(f"{'='*60}")
            print(f"📝 본문 내용:")
            print(f"{'-'*60}")
            print(post_content.get("content", "본문 없음"))
            print(f"{'-'*60}")
            print(f"{'='*60}\n")

            # 3. 스크롤 읽기
            stay_time = random.uniform(
                settings.get("min_stay_time", 60), settings.get("max_stay_time", 180)
            )
            print(f"3. 포스트 읽기 시작... ({int(stay_time)}초)")

            # 스크롤 전 모니터링
            if not self.monitor_browser_during_operation("스크롤 시작 전"):
                return False, "스크롤 시작 전 브라우저 종료됨"

            # 스크롤 모니터링 함수 호출
            self.read_with_scroll_monitored(
                stay_time, settings.get("scroll_speed", "보통")
            )

            # 4. 좋아요 및 댓글
            if settings.get("auto_like", True):
                if self.monitor_browser_during_operation("좋아요 전"):
                    like_success = self._click_like()
                    if like_success:
                        print("✓ 좋아요 클릭 완료")

            if settings.get("auto_comment", True):
                if not self.monitor_browser_during_operation("댓글 생성 전"):
                    return False, "댓글 생성 전 브라우저 종료됨"

                comment = self._generate_comment(
                    post_content["title"],
                    post_content["content"],
                    settings.get("comment_style", "친근함"),
                )

                if comment:
                    print(f"✓ 댓글 생성 완료: {comment[:100]}...")

                    if not self.monitor_browser_during_operation("댓글 작성 전"):
                        return False, "댓글 작성 전 브라우저 종료됨"

                    success = self._write_comment(comment)
                    if success:
                        print("✓ 댓글 작성 완료!")
                        return True, comment
                    else:
                        return False, "댓글 작성 실패"
                else:
                    return False, "댓글 생성 실패"
            else:
                return True, "포스트 방문 완료 (댓글 미작성)"

        except Exception as e:
            error_msg = f"포스트 처리 중 오류: {str(e)}"
            print(f"✗ {error_msg}")

            # 브라우저 상태 진단
            self.log_browser_status("오류 발생 후")

            return False, error_msg

    def read_with_scroll_monitored(self, duration: float, scroll_speed: str = "보통"):
        """브라우저 모니터링이 포함된 스크롤 읽기"""
        speeds = {
            "느리게": {"step": 100, "delay": 0.5},
            "보통": {"step": 200, "delay": 0.3},
            "빠르게": {"step": 300, "delay": 0.1},
        }

        speed_config = speeds.get(scroll_speed, speeds["보통"])
        start_time = time.time()
        scroll_count = 0
        monitor_interval = 20  # 20회 스크롤마다 모니터링

        try:
            total_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            current_position = 0

            while time.time() - start_time < duration and self.is_running:
                # 주기적 브라우저 모니터링
                if scroll_count % monitor_interval == 0:
                    if not self.monitor_browser_during_operation(
                        f"스크롤 중 ({scroll_count}회)"
                    ):
                        print(f"🚨 스크롤 중 브라우저 종료 감지됨!")
                        break

                remaining_time = duration - (time.time() - start_time)
                if remaining_time <= 0:
                    break

                scroll_distance = random.randint(
                    int(speed_config["step"] * 0.8), int(speed_config["step"] * 1.2)
                )

                try:
                    if current_position + scroll_distance >= total_height * 0.9:
                        self.driver.execute_script("window.scrollBy(0, -500);")
                        current_position -= 500
                    else:
                        self.driver.execute_script(
                            f"window.scrollBy(0, {scroll_distance});"
                        )
                        current_position += scroll_distance

                    time.sleep(speed_config["delay"])
                    scroll_count += 1

                except Exception as e:
                    print(f"✗ 스크롤 실행 중 오류: {e}")
                    if not self.check_browser_alive():
                        print("🚨 스크롤 중 브라우저 종료됨!")
                        break

            print(f"스크롤 완료 - 총 {scroll_count}회")

        except Exception as e:
            print(f"✗ 스크롤 중 오류: {e}")
            self.log_browser_status("스크롤 오류 후")

    def login_naver(self, user_id: str, password: str) -> Tuple[bool, str]:
        """네이버 로그인 - 개선된 버전"""
        try:
            print("네이버 로그인 시작...")

            # 1. 네이버 메인 → 로그인 페이지 순차 접근
            self.driver.get("https://www.naver.com")
            time.sleep(random.uniform(2, 4))

            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(random.uniform(3, 5))

            # 2. 로그인 폼 대기
            try:
                self.wait.until(EC.presence_of_element_located((By.ID, "id")))
                print("로그인 페이지 로드 완료")
            except:
                return False, "로그인 페이지 로드 실패"

            # 3. 입력 방식 (pyperclip → JS → send_keys 순)
            input_success = False

            # 방법 1: pyperclip 사용
            try:
                import pyperclip

                id_input = self.driver.find_element(By.ID, "id")
                id_input.click()
                time.sleep(0.5)
                pyperclip.copy(user_id)
                id_input.send_keys(Keys.CONTROL, "v")
                time.sleep(random.uniform(0.5, 1))

                pw_input = self.driver.find_element(By.ID, "pw")
                pw_input.click()
                time.sleep(0.5)
                pyperclip.copy(password)
                pw_input.send_keys(Keys.CONTROL, "v")
                time.sleep(random.uniform(0.5, 1))

                input_success = True
                print("클립보드를 통한 입력 완료")
            except Exception as e:
                print(f"클립보드 입력 실패: {e}")

            # 방법 2: JavaScript 직접 입력
            if not input_success:
                try:
                    self.driver.execute_script(
                        f"""
                        document.getElementById('id').value = '{user_id}';
                        document.getElementById('pw').value = '{password}';
                        """
                    )
                    time.sleep(1)
                    input_success = True
                    print("JavaScript를 통한 입력 완료")
                except Exception as e:
                    print(f"JavaScript 입력 실패: {e}")

            # 방법 3: send_keys 최후 수단
            if not input_success:
                try:
                    id_input = self.driver.find_element(By.ID, "id")
                    id_input.clear()
                    for char in user_id:
                        id_input.send_keys(char)
                        time.sleep(random.uniform(0.1, 0.2))

                    pw_input = self.driver.find_element(By.ID, "pw")
                    pw_input.clear()
                    for char in password:
                        pw_input.send_keys(char)
                        time.sleep(random.uniform(0.1, 0.2))

                    input_success = True
                    print("일반 키보드 입력 완료")
                except Exception as e:
                    return False, f"모든 입력 방식 실패: {e}"

            # 4. 로그인 상태 유지 체크박스 클릭
            try:
                keep_login = self.driver.find_element(By.CSS_SELECTOR, ".keep_check")
                if keep_login and not keep_login.is_selected():
                    self.driver.execute_script("arguments[0].click();", keep_login)
                    time.sleep(0.5)
                    print("로그인 상태 유지 체크")
            except:
                pass

            # 5. 로그인 버튼 클릭 (Enter → ID/비밀번호 form → CSS 등 다중 시도)
            login_success = False

            # 방법 1: Enter 키
            try:
                pw_input.send_keys(Keys.ENTER)
                login_success = True
                print("Enter 키로 로그인 시도")
            except:
                pass

            # 방법 2: 버튼 직접 클릭
            if not login_success:
                try:
                    login_btn = self.driver.find_element(By.ID, "log.login")
                    self.driver.execute_script("arguments[0].click();", login_btn)
                    login_success = True
                    print("로그인 버튼 클릭")
                except:
                    pass

            # 방법 3: CSS 선택자
            if not login_success:
                try:
                    login_btn = self.driver.find_element(By.CSS_SELECTOR, ".btn_login")
                    login_btn.click()
                    login_success = True
                    print("CSS 선택자로 로그인 버튼 클릭")
                except:
                    pass

            if not login_success:
                return False, "로그인 버튼 클릭 실패"

            # 6. 로그인 결과 확인 (충분 대기)
            print("로그인 결과 확인 중...")
            time.sleep(random.uniform(5, 8))

            current_url = self.driver.current_url
            print(f"현재 URL: {current_url}")

            success_conditions = [
                "naver.com" in current_url and "nid.naver.com" not in current_url,
                "blog.naver.com" in current_url,
                "mail.naver.com" in current_url,
                self.check_login_status(),
            ]

            if any(success_conditions):
                self.is_logged_in = True
                print("로그인 성공 확인됨")
                return True, "로그인 성공"

            # 실패 원인별 메시지
            if "captcha" in current_url.lower():
                return False, "캡차 인증이 필요합니다. 수동 로그인 모드를 사용해주세요."
            if "protect" in current_url or "security" in current_url:
                return False, "보안 인증이 필요합니다. 수동 로그인 모드를 사용해주세요."
            if "changepassword" in current_url:
                return False, "비밀번호 변경이 필요합니다."

            # 화면 상 에러 메시지 확인
            try:
                error_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, ".error_message, .err_text, .login_error"
                )
                for elem in error_elements:
                    if elem.is_displayed() and elem.text.strip():
                        return False, f"로그인 실패: {elem.text.strip()}"
            except:
                pass

            return (
                False,
                f"로그인 실패 - 현재 URL: {current_url}. 수동 로그인을 시도해보세요.",
            )

        except Exception as e:
            return False, f"로그인 중 오류: {str(e)}"

    def check_login_status(self) -> bool:
        """로그인 상태 확인 헬퍼 메서드"""
        try:
            login_indicators = [
                ".MyView-module__my_menu___ehoqV",  # 마이메뉴
                ".MyView-module__link_logout___tBXTU",  # 로그아웃 버튼
                "#account",  # 계정 영역
                ".user_info",  # 사용자 정보
                ".gnb_my",  # 내 정보
            ]

            for selector in login_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(elem.is_displayed() for elem in elements):
                        return True
                except:
                    continue

            return False
        except:
            return False

    def manual_login_wait(self) -> Tuple[bool, str]:
        """수동 로그인 대기 모드"""
        try:
            print("수동 로그인 모드 시작")
            print("브라우저에서 직접 로그인해주세요...")

            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)

            input("로그인 완료 후 Enter를 누르세요...")

            if self.check_login_status():
                self.is_logged_in = True
                return True, "수동 로그인 성공"
            else:
                # 네이버 메인으로 이동 후 재확인
                self.driver.get("https://www.naver.com")
                time.sleep(3)
                if self.check_login_status():
                    self.is_logged_in = True
                    return True, "수동 로그인 성공"
                else:
                    return False, "로그인 상태를 확인할 수 없습니다"

        except Exception as e:
            return False, f"수동 로그인 중 오류: {str(e)}"

    def get_neighbor_new_posts(self) -> List[Dict]:
        """이웃 새글 가져오기 - 구문 오류 수정 및 디버깅 강화"""
        try:
            print("이웃 새글 페이지 접속 중...")

            self.driver.get("https://section.blog.naver.com/BlogHome.naver")
            time.sleep(3)

            current_url = self.driver.current_url
            print(f"현재 URL: {current_url}")

            posts: List[Dict] = []

            # 방법 1: title_post 클래스 기반 추출
            try:
                print("title_post 클래스 기반 포스팅 검색 중...")
                title_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, ".title_post"
                )
                print(f"title_post 요소 발견: {len(title_elements)}개")

                for title_elem in title_elements:
                    try:
                        parent_link = None
                        current_elem = title_elem

                        # 최대 5단계까지 부모 탐색
                        for _ in range(5):
                            try:
                                current_elem = current_elem.find_element(By.XPATH, "..")
                                if current_elem.tag_name == "a":
                                    href = current_elem.get_attribute("href")
                                    if href and "blog.naver.com" in href:
                                        parent_link = current_elem
                                        break
                            except:
                                break

                        # 부모 a태그가 없으면 컨테이너 내에서 찾기
                        if not parent_link:
                            try:
                                container = title_elem.find_element(By.XPATH, "../..")
                                links = container.find_elements(
                                    By.CSS_SELECTOR, "a[href*='blog.naver.com']"
                                )
                                if links:
                                    parent_link = links[0]
                            except:
                                continue

                        if parent_link:
                            url = parent_link.get_attribute("href")
                            title = title_elem.text.strip()

                            if (
                                url
                                and title
                                and len(title) > 3
                                and (
                                    "PostView" in url
                                    or "logNo" in url
                                    or url.count("/") >= 4
                                )
                            ):
                                # 블로거 이름 찾기
                                blogger = "Unknown"
                                try:
                                    container = title_elem.find_element(
                                        By.XPATH, "../.."
                                    )
                                    blogger_selectors = [
                                        ".nick",
                                        ".name",
                                        ".writer",
                                        ".author",
                                        "[class*='nick']",
                                        "[class*='name']",
                                        "[class*='writer']",
                                        ".blog_name",
                                        ".user_name",
                                    ]
                                    for blogger_selector in blogger_selectors:
                                        try:
                                            blogger_elems = container.find_elements(
                                                By.CSS_SELECTOR, blogger_selector
                                            )
                                            for blogger_elem in blogger_elems:
                                                text = blogger_elem.text.strip()
                                                if (
                                                    text
                                                    and text != title
                                                    and 2 <= len(text) <= 20
                                                ):
                                                    blogger = text
                                                    break
                                            if blogger != "Unknown":
                                                break
                                        except:
                                            continue
                                except:
                                    pass

                                if not any(p["url"] == url for p in posts):
                                    posts.append(
                                        {
                                            "title": title,
                                            "url": url,
                                            "blogger": blogger,
                                            "index": len(posts),
                                        }
                                    )
                                    print(f"포스팅 발견: [{blogger}] {title[:30]}...")
                    except Exception as e:
                        print(f"title_post 요소 처리 중 오류: {e}")
                        continue

            except Exception as e:
                print(f"title_post 기반 검색 오류: {e}")

            # 방법 2: 추가 포스팅 검색 (컨테이너 기반)
            if len(posts) < 10:
                print("추가 포스팅 검색 중...")
                try:
                    post_containers = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "section.wrap_thumbnail_post_list, .list_post, .post_list, .neighbor_post",
                    )

                    for container in post_containers:
                        try:
                            links = container.find_elements(
                                By.CSS_SELECTOR, "a[href*='blog.naver.com']"
                            )

                            for link in links:
                                try:
                                    url = link.get_attribute("href")
                                    if not (
                                        url and ("PostView" in url or "logNo" in url)
                                    ):
                                        continue
                                    if any(p["url"] == url for p in posts):
                                        continue

                                    title = ""
                                    title_sources = [
                                        link.text.strip(),
                                        link.get_attribute("title"),
                                        link.get_attribute("alt"),
                                    ]
                                    try:
                                        title_elems = link.find_elements(
                                            By.CSS_SELECTOR,
                                            ".title_post, .post_title, [class*='title'], h3, h4, span",
                                        )
                                        for elem in title_elems:
                                            text = elem.text.strip()
                                            if text and len(text) > 3:
                                                title_sources.append(text)
                                    except:
                                        pass

                                    for title_candidate in title_sources:
                                        if title_candidate and len(title_candidate) > 3:
                                            title = title_candidate
                                            break
                                    if not title:
                                        continue

                                    blogger = "Unknown"
                                    try:
                                        parent = link.find_element(By.XPATH, "../..")
                                        blogger_elems = parent.find_elements(
                                            By.CSS_SELECTOR,
                                            ".nick, .name, .writer, .author, .blog_name",
                                        )
                                        for elem in blogger_elems:
                                            text = elem.text.strip()
                                            if (
                                                text
                                                and text != title
                                                and 2 <= len(text) <= 20
                                            ):
                                                blogger = text
                                                break
                                    except:
                                        pass

                                    posts.append(
                                        {
                                            "title": title,
                                            "url": url,
                                            "blogger": blogger,
                                            "index": len(posts),
                                        }
                                    )

                                    if len(posts) >= 15:
                                        break

                                except Exception as e:
                                    print(f"링크 처리 중 오류: {e}")
                                    continue

                            if len(posts) >= 15:
                                break

                        except Exception as e:
                            print(f"컨테이너 처리 중 오류: {e}")
                            continue

                except Exception as e:
                    print(f"추가 포스팅 검색 오류: {e}")

            # 방법 3: JavaScript 기반 검색
            if len(posts) < 5:
                print("JavaScript 기반 포스팅 검색...")
                try:
                    js_code = """
                    var posts = [];
                    var titleElements = document.querySelectorAll('.title_post');
                    for (var i = 0; i < titleElements.length && posts.length < 15; i++) {
                        var titleElem = titleElements[i];
                        var title = titleElem.textContent.trim();
                        if (!title || title.length < 3) continue;

                        var parentLink = null;
                        var current = titleElem;
                        for (var j = 0; j < 5; j++) {
                            current = current.parentElement;
                            if (!current) break;
                            if (current.tagName === 'A' && current.href && 
                                current.href.includes('blog.naver.com')) {
                                parentLink = current;
                                break;
                            }
                        }

                        if (!parentLink) {
                            var container = titleElem.closest('div, li, article');
                            if (container) {
                                var links = container.querySelectorAll('a[href*="blog.naver.com"]');
                                for (var k = 0; k < links.length; k++) {
                                    if (links[k].href.includes('PostView') || links[k].href.includes('logNo')) {
                                        parentLink = links[k];
                                        break;
                                    }
                                }
                            }
                        }

                        if (parentLink && (parentLink.href.includes('PostView') || 
                            parentLink.href.includes('logNo'))) {

                            var blogger = 'Unknown';
                            var container = titleElem.closest('div, li, article');
                            if (container) {
                                var bloggerElems = container.querySelectorAll('.nick, .name, .writer, .author, .blog_name');
                                for (var l = 0; l < bloggerElems.length; l++) {
                                    var text = bloggerElems[l].textContent.trim();
                                    if (text && text !== title && text.length >= 2 && text.length <= 20) {
                                        blogger = text;
                                        break;
                                    }
                                }
                            }

                            var isDuplicate = false;
                            for (var m = 0; m < posts.length; m++) {
                                if (posts[m].url === parentLink.href) {
                                    isDuplicate = true;
                                    break;
                                }
                            }

                            if (!isDuplicate) {
                                posts.push({
                                    title: title,
                                    url: parentLink.href,
                                    blogger: blogger,
                                    index: posts.length
                                });
                            }
                        }
                    }
                    return posts;
                    """
                    js_posts = self.driver.execute_script(js_code)
                    if js_posts:
                        for jp in js_posts:
                            if not any(p["url"] == jp["url"] for p in posts):
                                posts.append(jp)
                                if len(posts) >= 15:
                                    break
                        print(f"JavaScript로 {len(js_posts)}개 포스트 추가")
                except Exception as e:
                    print(f"JavaScript 검색 오류: {e}")

            print(f"\n총 {len(posts)}개의 포스트를 발견했습니다.")

            for i, post in enumerate(posts[:5]):
                print(f"\n포스트 {i+1}:")
                print(f"  제목: {post['title'][:50]}...")
                print(f"  작성자: {post['blogger']}")
                print(f"  URL: {post['url'][:80]}...")

            if len(posts) > 5:
                print(f"\n... 외 {len(posts)-5}개 더")

            return posts

        except Exception as e:
            print(f"이웃 새글 가져오기 실패: {e}")
            import traceback

            traceback.print_exc()
            return []

    def collect_post_info(self) -> Optional[Dict]:
        """포스트 정보 수집 - 디버깅 강화"""
        try:
            print("\n=== 포스트 정보 수집 시작 ===")
            iframe_found = False

            # iframe 전환 시도
            try:
                iframe = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(iframe)
                iframe_found = True
                print("mainFrame iframe 전환 성공")
            except:
                iframe_list = self.driver.find_elements(By.TAG_NAME, "iframe")
                print(f"발견된 iframe 수: {len(iframe_list)}")
                if iframe_list:
                    for i, iframe in enumerate(iframe_list):
                        try:
                            size = iframe.size
                            print(f"iframe {i}: 크기 {size}")
                            if size["width"] > 500 and size["height"] > 500:
                                self.driver.switch_to.frame(iframe)
                                iframe_found = True
                                print(f"큰 iframe {i} 전환 성공")
                                break
                        except:
                            continue

                    if not iframe_found and iframe_list:
                        try:
                            self.driver.switch_to.frame(iframe_list[0])
                            iframe_found = True
                            print("첫 번째 iframe 전환 성공")
                        except:
                            pass

            # 제목 수집
            title = ""
            title_selectors = [
                ".se-title-text",
                ".se-fs-.se-ff-",
                ".htitle",
                "h3.se-fs-",
                ".pcol1",
                ".se-module-text h1",
                ".se-module-text h2",
                ".se-module-text h3",
                ".title_post",  # 추가
            ]

            print(f"제목 찾기 시도 중... (선택자 {len(title_selectors)}개)")
            for i, selector in enumerate(title_selectors):
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    title = title_elem.text.strip()
                    if title:
                        print(
                            f"✓ 제목 추출 성공 ({i+1}/{len(title_selectors)}): {selector}"
                        )
                        print(f"  제목: {title[:100]}...")
                        break
                    else:
                        print(f"✗ 제목 빈값 ({i+1}/{len(title_selectors)}): {selector}")
                except Exception as e:
                    print(
                        f"✗ 제목 선택자 실패 ({i+1}/{len(title_selectors)}): {selector} - {e}"
                    )
                    continue

            # 본문 수집
            content = ""
            content_selectors = [
                ".se-main-container",
                ".se-text-paragraph",
                "#postViewArea",
                ".post-view",
                ".post_ct",
                ".se-module-text",
                ".se-component-wrap",  # 추가
            ]

            print(f"\n본문 찾기 시도 중... (선택자 {len(content_selectors)}개)")
            for i, selector in enumerate(content_selectors):
                try:
                    content_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    print(f"선택자 {selector}: {len(content_elements)}개 요소 발견")

                    if content_elements:
                        content_parts = []
                        for elem in content_elements:
                            text = elem.text.strip()
                            if text:
                                content_parts.append(text)

                        content = "\n".join(content_parts)
                        if content:
                            print(
                                f"✓ 본문 추출 성공 ({i+1}/{len(content_selectors)}): {selector}"
                            )
                            print(f"  본문 길이: {len(content)}자")
                            print(f"  본문 미리보기: {content[:200]}...")
                            break
                        else:
                            print(
                                f"✗ 본문 빈값 ({i+1}/{len(content_selectors)}): {selector}"
                            )
                except Exception as e:
                    print(
                        f"✗ 본문 선택자 실패 ({i+1}/{len(content_selectors)}): {selector} - {e}"
                    )
                    continue

            # 메인 프레임으로 복귀
            if iframe_found:
                self.driver.switch_to.default_content()
                print("메인 프레임으로 복귀")

            print(f"\n=== 수집 결과 ===")
            print(f"제목 수집: {'성공' if title else '실패'}")
            print(f"본문 수집: {'성공' if content else '실패'}")

            if title and content:
                result = {
                    "title": title,
                    "content": content[:2000],  # 최대 2000자로 제한
                }
                print(
                    f"최종 반환 데이터: 제목 {len(title)}자, 본문 {len(result['content'])}자"
                )
                return result
            else:
                print("포스트 정보 수집 실패")
                try:
                    page_source = self.driver.page_source[:1000]
                    print(f"페이지 소스 미리보기: {page_source}...")
                except:
                    pass
                return None

        except Exception as e:
            print(f"포스트 정보 수집 중 오류: {str(e)}")
            import traceback

            traceback.print_exc()
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return None

    def _generate_comment(self, title: str, content: str, style: str = "친근함") -> str:
        """댓글 생성 - 디버깅 강화"""
        try:
            print(f"\n=== 댓글 생성 시작 ===")
            print(f"제목: {title[:50]}...")
            print(f"내용 길이: {len(content)}자")
            print(f"스타일: {style}")

            # CachedCommentGenerator 사용 (생략된 부분)

            # 기본 Claude 클라이언트 사용 (생략된 부분)

            # API가 없으면 기본 댓글
            print("API 없음 - 기본 댓글 사용")
            fallback_comments = [
                "좋은 글 잘 읽었습니다! 😊",
                "유익한 정보 감사해요 👍",
                "정말 도움이 되는 내용이네요!",
                "좋은 글 공유해주셔서 감사합니다 ✨",
                "잘 보고 갑니다~ 좋은 하루 되세요!",
                "멋진 포스팅이네요! 👏",
            ]
            comment = random.choice(fallback_comments)
            print(f"기본 댓글 선택: {comment}")
            return comment

        except Exception as e:
            print(f"댓글 생성 실패: {e}")
            import traceback

            traceback.print_exc()
            return "좋은 글 잘 읽었습니다! 😊"

    def _click_like(self) -> bool:
        """좋아요 버튼 클릭"""
        try:
            # iframe 전환
            self._switch_to_content_frame()

            like_selectors = [
                ".u_likeit_button",
                ".u_ico_like",
                ".btn_like",
                ".like_on",
                "#area_like_btn",
                "button[data-type='like']",
                ".btn_sympathy",
                ".ico_like",
            ]

            for selector in like_selectors:
                try:
                    like_btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for like_btn in like_btns:
                        if like_btn and like_btn.is_displayed():
                            class_name = like_btn.get_attribute("class") or ""
                            if (
                                "on" in class_name
                                or "active" in class_name
                                or "pressed" in class_name
                            ):
                                print("이미 좋아요를 누른 포스트입니다.")
                                self.driver.switch_to.default_content()
                                return True

                            self.driver.execute_script(
                                "arguments[0].scrollIntoView(true);", like_btn
                            )
                            time.sleep(0.5)
                            self.driver.execute_script(
                                "arguments[0].click();", like_btn
                            )
                            time.sleep(1)
                            self.driver.switch_to.default_content()
                            return True
                except Exception as e:
                    print(f"좋아요 버튼 클릭 시도 실패 ({selector}): {e}")
                    continue

            self.driver.switch_to.default_content()
            print("좋아요 버튼을 찾을 수 없습니다.")
            return False

        except Exception as e:
            print(f"좋아요 클릭 실패: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def _write_comment(self, comment_text: str) -> bool:
        """댓글 작성"""
        try:
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(3)

            comment_frame_found = False

            # 댓글 iframe 찾기
            iframe_selectors = [
                "#naverComment",
                "#commentIframe",
                "iframe[title*='댓글']",
                "iframe[src*='comment']",
            ]

            for selector in iframe_selectors:
                try:
                    comment_frame = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.switch_to.frame(comment_frame)
                    comment_frame_found = True
                    print(f"댓글 iframe 전환 성공: {selector}")
                    break
                except:
                    continue

            # 없는 경우 모든 iframe 순회
            if not comment_frame_found:
                iframe_list = self.driver.find_elements(By.TAG_NAME, "iframe")
                for i, iframe in enumerate(iframe_list):
                    try:
                        self.driver.switch_to.frame(iframe)
                        inputs = self.driver.find_elements(
                            By.CSS_SELECTOR, ".u_cbox_text, .comment_inbox_text"
                        )
                        if inputs:
                            comment_frame_found = True
                            print(f"댓글 iframe 발견 (index {i})")
                            break
                        else:
                            self.driver.switch_to.default_content()
                    except:
                        try:
                            self.driver.switch_to.default_content()
                        except:
                            pass
                        continue

            # 댓글 입력창 찾기
            comment_input = None
            input_selectors = [
                ".u_cbox_text",
                ".comment_inbox_text",
                "textarea[placeholder*='댓글']",
                "textarea[placeholder*='comment']",
                ".cmt_textarea",
                ".comment_textarea",
            ]

            for selector in input_selectors:
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for input_elem in inputs:
                        if input_elem.is_displayed() and input_elem.is_enabled():
                            comment_input = input_elem
                            print(f"댓글 입력창 발견: {selector}")
                            break
                    if comment_input:
                        break
                except:
                    continue

            if not comment_input:
                print("댓글 입력창을 찾을 수 없습니다.")
                self.driver.switch_to.default_content()
                return False

            # 댓글 입력
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView(true);", comment_input
                )
                time.sleep(1)

                self.driver.execute_script("arguments[0].click();", comment_input)
                time.sleep(1)

                comment_input.clear()
                time.sleep(0.5)

                for char in comment_text:
                    comment_input.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.15))

                time.sleep(1)
                print("댓글 입력 완료")
            except Exception as e:
                print(f"댓글 입력 실패: {e}")
                self.driver.switch_to.default_content()
                return False

            # 등록 버튼 찾기
            submit_selectors = [
                ".u_cbox_btn_upload",
                ".btn_register",
                "button[type='submit']",
                ".cmt_btn_register",
                ".comment_btn_submit",
                "input[value='등록']",
            ]

            submit_clicked = False
            for selector in submit_selectors:
                try:
                    submit_btns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for submit_btn in submit_btns:
                        if (
                            submit_btn
                            and submit_btn.is_displayed()
                            and submit_btn.is_enabled()
                        ):
                            self.driver.execute_script(
                                "arguments[0].click();", submit_btn
                            )
                            submit_clicked = True
                            print(f"댓글 등록 버튼 클릭: {selector}")
                            break
                    if submit_clicked:
                        break
                except:
                    continue

            if not submit_clicked:
                try:
                    comment_input.send_keys(Keys.ENTER)
                    submit_clicked = True
                    print("Enter 키로 댓글 등록")
                except:
                    pass

            if not submit_clicked:
                print("댓글 등록 버튼을 찾을 수 없습니다.")
                self.driver.switch_to.default_content()
                return False

            time.sleep(3)
            self.driver.switch_to.default_content()
            return True

        except Exception as e:
            print(f"댓글 작성 실패: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def _switch_to_content_frame(self) -> bool:
        """콘텐츠 iframe으로 전환하는 헬퍼 메서드"""
        try:
            try:
                main_frame = self.driver.find_element(By.ID, "mainFrame")
                self.driver.switch_to.frame(main_frame)
                return True
            except:
                pass

            iframe_list = self.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframe_list:
                try:
                    size = iframe.size
                    if size["width"] > 500 and size["height"] > 500:
                        self.driver.switch_to.frame(iframe)
                        return True
                except:
                    continue

            return False
        except:
            return False

    def read_with_scroll(self, duration: float, scroll_speed: str = "보통"):
        """자연스러운 스크롤 시뮬레이션 (모니터링 포함)"""
        speeds = {
            "느리게": {"step": 100, "delay": 0.5},
            "보통": {"step": 200, "delay": 0.3},
            "빠르게": {"step": 300, "delay": 0.1},
        }

        speed_config = speeds.get(scroll_speed, speeds["보통"])
        start_time = time.time()
        scroll_count = 0

        try:
            total_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            current_position = 0
            print(f"스크롤 시작 - 전체 높이: {total_height}px, 지속시간: {duration}초")

            while time.time() - start_time < duration and self.is_running:
                # 매 10회 스크롤마다 상태 확인
                if scroll_count % 10 == 0:
                    try:
                        self.driver.execute_script("return document.readyState")
                        remaining_time = duration - (time.time() - start_time)
                        if scroll_count > 0:
                            print(
                                f"스크롤 진행 중... (남은 시간: {int(remaining_time)}초, 스크롤: {scroll_count}회)"
                            )
                    except Exception as e:
                        print(f"✗ 스크롤 중 브라우저 상태 확인 실패: {e}")
                        break

                remaining_time = duration - (time.time() - start_time)
                if remaining_time <= 0:
                    break

                scroll_distance = random.randint(
                    int(speed_config["step"] * 0.8), int(speed_config["step"] * 1.2)
                )

                try:
                    if current_position + scroll_distance >= total_height * 0.9:
                        self.driver.execute_script("window.scrollBy(0, -500);")
                        current_position -= 500
                        time.sleep(random.uniform(1, 2))
                    else:
                        self.driver.execute_script(
                            f"window.scrollBy(0, {scroll_distance});"
                        )
                        current_position += scroll_distance

                    time.sleep(speed_config["delay"])
                    scroll_count += 1

                    # 가끔 위로 스크롤 (20% 확률)
                    if random.random() < 0.2:
                        back_distance = speed_config["step"] // 2
                        self.driver.execute_script(
                            f"window.scrollBy(0, -{back_distance});"
                        )
                        current_position -= back_distance
                        time.sleep(speed_config["delay"] * 2)

                    # 가끔 멈춤 (30% 확률)
                    if random.random() < 0.3:
                        pause_time = random.uniform(1, min(3, remaining_time))
                        time.sleep(pause_time)

                    # 높이 재계산 (50회마다)
                    if scroll_count % 50 == 0:
                        total_height = self.driver.execute_script(
                            "return document.body.scrollHeight"
                        )

                except Exception as e:
                    print(f"✗ 스크롤 실행 중 오류: {e}")
                    break

            print(
                f"스크롤 완료 - 총 {scroll_count}회 스크롤, 소요시간: {time.time() - start_time:.1f}초"
            )

        except Exception as e:
            print(f"✗ 스크롤 시뮬레이션 중 오류: {e}")
            import traceback

            traceback.print_exc()

    def check_browser_status(self, operation_name: str = "작업") -> bool:
        """브라우저 상태 확인 헬퍼 메서드"""
        try:
            current_url = self.driver.current_url
            ready_state = self.driver.execute_script("return document.readyState")
            window_handles = self.driver.window_handles

            print(f"✓ {operation_name} 브라우저 상태 정상")
            print(f"  - URL: {current_url[:100]}...")
            print(f"  - Ready State: {ready_state}")
            print(f"  - Window Handles: {len(window_handles)}개")
            return True

        except Exception as e:
            print(f"✗ {operation_name} 브라우저 상태 확인 실패: {e}")
            return False

    def close(self):
        """브라우저 종료 - 모니터링 포함"""
        self.is_running = False

        # 모니터링 중지
        if self.browser_monitor:
            self.browser_monitor.stop_monitoring()
            summary = self.browser_monitor.get_summary()
            print(f"\n📊 브라우저 모니터링 요약:")
            print(f"  총 크래시 감지: {summary['crashes']}회")
            print(f"  시스템 경고: {summary['system_alerts']}회")
            if summary["last_crash"]:
                print(f"  마지막 크래시: {summary['last_crash']['timestamp']}")

        if self.driver:
            try:
                print("브라우저 종료 중...")
                try:
                    current_url = self.driver.current_url
                    print(f"종료 전 마지막 URL: {current_url[:100]}...")
                except:
                    print("브라우저가 이미 비정상 상태입니다.")

                self.driver.quit()
                print("✓ 브라우저 정상 종료 완료")
            except Exception as e:
                print(f"✗ 브라우저 종료 중 오류: {e}")
                print("Chrome 프로세스 강제 종료 시도...")
                try:
                    import subprocess
                    import platform

                    if platform.system() == "Windows":
                        subprocess.run(
                            ["taskkill", "/f", "/im", "chrome.exe"],
                            capture_output=True,
                            timeout=10,
                        )
                        subprocess.run(
                            ["taskkill", "/f", "/im", "chromedriver.exe"],
                            capture_output=True,
                            timeout=10,
                        )
                    else:
                        subprocess.run(
                            ["pkill", "-f", "chrome"], capture_output=True, timeout=10
                        )
                        subprocess.run(
                            ["pkill", "-f", "chromedriver"],
                            capture_output=True,
                            timeout=10,
                        )

                    print("✓ Chrome 프로세스 강제 종료 완료")
                except Exception as cleanup_error:
                    print(f"강제 종료도 실패: {cleanup_error}")


def test_login(user_id: str, password: str, headless: bool = False):
    """로그인 테스트 함수"""
    automation = NaverBlogAutomation(headless=headless)

    if automation.init_browser():
        success, message = automation.login_naver(user_id, password)
        print(f"로그인 결과: {success}, 메시지: {message}")

        if success:
            posts = automation.get_neighbor_new_posts()
            print(f"발견된 포스트 수: {len(posts)}")
            for i, post in enumerate(posts[:3]):
                print(f"{i+1}. {post['title']} - {post['blogger']}")

        input("Enter를 눌러 브라우저를 종료합니다...")
        automation.close()
    else:
        print("브라우저 초기화 실패")


if __name__ == "__main__":
    # 테스트 실행
    print("네이버 블로그 자동화 모듈 테스트")
    # 실제 사용 시 아이디/비밀번호 입력 후 주석 해제
    # test_login("your_naver_id", "your_password", headless=False)
