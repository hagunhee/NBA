import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import platform
import uuid
import psutil
import json
import os
from datetime import datetime, timedelta
import threading
import requests
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import anthropic


class FirestoreSecurityManager:
    """Firestore 기반 보안 및 라이선스 관리"""

    def __init__(self, firebase_config_path="serviceAccountKey.json"):
        self.db = None
        self.firebase_config_path = firebase_config_path
        self.init_firebase()

    def init_firebase(self):
        """Firebase 초기화"""
        try:
            # Firebase 앱이 이미 초기화되었는지 확인
            if not firebase_admin._apps:
                # 서비스 계정 키 파일로 초기화
                if os.path.exists(self.firebase_config_path):
                    cred = credentials.Certificate(self.firebase_config_path)
                    firebase_admin.initialize_app(cred)
                else:
                    print(
                        f"Firebase 설정 파일을 찾을 수 없습니다: {self.firebase_config_path}"
                    )
                    return False

            self.db = firestore.client()
            print("Firebase 연결 성공")
            return True

        except Exception as e:
            print(f"Firebase 초기화 실패: {e}")
            return False

    def get_hardware_id(self):
        """하드웨어 고유 ID 생성 (WMI 대신 안전한 방법 사용)"""
        try:
            # 다양한 시스템 정보 수집
            system_info = []

            # 플랫폼 정보
            system_info.append(platform.machine())
            system_info.append(platform.processor())
            system_info.append(platform.system())

            # MAC 주소 (네트워크 인터페이스)
            try:
                mac = hex(uuid.getnode())
                system_info.append(mac)
            except:
                pass

            # 메모리 정보
            try:
                memory = psutil.virtual_memory()
                system_info.append(str(memory.total))
            except:
                pass

            # 디스크 정보
            try:
                disk_usage = psutil.disk_usage("/")
                system_info.append(str(disk_usage.total))
            except:
                pass

            # Windows 특정 정보 (WMI 없이)
            if platform.system() == "Windows":
                try:
                    import subprocess

                    # Windows 시스템 정보
                    result = subprocess.run(
                        ["wmic", "csproduct", "get", "uuid"],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        uuid_info = result.stdout.strip().split("\n")
                        if len(uuid_info) > 1:
                            system_info.append(uuid_info[1].strip())
                except:
                    pass

            # 모든 정보를 결합하여 해시 생성
            combined_info = "".join(system_info)
            hardware_id = hashlib.sha256(combined_info.encode()).hexdigest()

            return hardware_id

        except Exception as e:
            print(f"하드웨어 ID 생성 실패: {e}")
            # 기본 fallback
            fallback_info = (
                f"{platform.machine()}-{platform.system()}-{hex(uuid.getnode())}"
            )
            return hashlib.md5(fallback_info.encode()).hexdigest()

    def verify_license_online(self, license_key):
        """온라인으로 라이선스 검증"""
        if not self.db:
            return False, "Firebase 연결 실패"

        try:
            # Firestore에서 라이선스 정보 조회
            license_ref = self.db.collection("licenses").document(license_key)
            license_doc = license_ref.get()

            if not license_doc.exists:
                return False, "존재하지 않는 라이선스입니다."

            license_data = license_doc.to_dict()

            # 활성화 상태 확인
            if not license_data.get("active", False):
                return False, "비활성화된 라이선스입니다."

            # 만료일 확인
            expire_date = license_data.get("expire_date")
            if expire_date and isinstance(expire_date, str):
                expire_datetime = datetime.fromisoformat(expire_date)
                if datetime.now() > expire_datetime:
                    return False, "만료된 라이선스입니다."

            # 하드웨어 ID 확인 및 등록
            current_hardware_id = self.get_hardware_id()
            stored_hardware_id = license_data.get("hardware_id")

            if not stored_hardware_id:
                # 첫 번째 사용 - 하드웨어 ID 등록
                license_ref.update(
                    {
                        "hardware_id": current_hardware_id,
                        "first_used": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                    }
                )
                print("하드웨어 ID가 등록되었습니다.")
            elif stored_hardware_id != current_hardware_id:
                return False, "다른 컴퓨터에서는 사용할 수 없는 라이선스입니다."
            else:
                # 마지막 사용 시간 업데이트
                license_ref.update({"last_used": datetime.now().isoformat()})

            return True, license_data

        except Exception as e:
            return False, f"라이선스 검증 중 오류: {str(e)}"


class NaverBlogAutomation:
    """네이버 블로그 자동화 실제 구현"""

    def __init__(self, headless=False):
        self.driver = None
        self.headless = headless
        self.is_logged_in = False
        self.claude_api_key = os.getenv('ANTHROPIC_API_KEY')  # 환경 변수에서 가져오기
        
        if not self.claude_api_key:
            # 하드코딩된 API 키 (보안을 위해 환경 변수 사용 권장)
            self.claude_api_key = "YOUR_CLAUDE_API_KEY_HERE"
        
        self.comment_generator = ClaudeCommentGenerator(self.claude_api_key)

    def setup_driver(self):
        """Chrome 드라이버 설정"""
        options = Options()
        if self.headless:
            options.add_argument("--headless")

        # 기본 옵션들
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # User-Agent 설정
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            return True
        except Exception as e:
            print(f"드라이버 설정 실패: {e}")
            return False

    def login_naver(self, user_id, password):
        """네이버 로그인"""
        try:
            self.driver.get("https://nid.naver.com/nidlogin.login")
            time.sleep(2)

            # 로그인 폼이 로드될 때까지 대기
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "id"))
            )

            # JavaScript로 입력 (Selenium 탐지 우회)
            self.driver.execute_script(
                f"document.getElementById('id').value = '{user_id}';"
            )
            time.sleep(1)
            self.driver.execute_script(
                f"document.getElementById('pw').value = '{password}';"
            )
            time.sleep(1)

            # 로그인 버튼 클릭
            login_btn = self.driver.find_element(By.ID, "log.login")
            self.driver.execute_script("arguments[0].click();", login_btn)

            # 로그인 결과 대기
            time.sleep(5)

            # 로그인 성공 여부 확인
            current_url = self.driver.current_url

            if "nid.naver.com" not in current_url or "naver.com" in current_url:
                self.is_logged_in = True
                return True, "로그인 성공"
            elif "captcha" in current_url:
                return False, "캡차 인증이 필요합니다"
            else:
                return False, "로그인 실패 - 아이디/비밀번호를 확인해주세요"

        except Exception as e:
            return False, f"로그인 중 오류: {str(e)}"

    def get_neighbor_new_posts(self):
        """이웃 새글 가져오기"""
        try:
            # 이웃 새글 페이지로 이동
            self.driver.get("https://section.blog.naver.com/BlogHome.naver?tab=following")
            time.sleep(3)

            # 포스트 목록 가져오기
            posts = []
            post_elements = self.driver.find_elements(By.CSS_SELECTOR, ".list_post_article")
            
            for element in post_elements[:10]:  # 최대 10개만 처리
                try:
                    # 포스트 제목과 링크 추출
                    title_element = element.find_element(By.CSS_SELECTOR, ".title_post")
                    title = title_element.text
                    link = title_element.get_attribute("href")
                    
                    # 블로거 이름 추출
                    blogger_element = element.find_element(By.CSS_SELECTOR, ".name_blog")
                    blogger = blogger_element.text
                    
                    posts.append({
                        'title': title,
                        'url': link,
                        'blogger': blogger
                    })
                except Exception as e:
                    print(f"포스트 정보 추출 실패: {e}")
                    continue
            
            return posts
        
        except Exception as e:
            print(f"이웃 새글 가져오기 실패: {e}")
            return []

    def process_post(self, post_info, comment_style="친근함"):
        """포스트 방문 및 댓글 작성"""
        try:
            # 포스트 페이지로 이동
            self.driver.get(post_info['url'])
            time.sleep(random.uniform(3, 5))

            # 본문 내용 가져오기
            content = self.get_post_content()
            
            # 스크롤하며 읽기 시뮬레이션
            self.simulate_reading()
            
            # 좋아요 누르기
            self.click_like()
            
            # 댓글 생성 및 작성
            if content:
                comment = self.comment_generator.generate_comment(
                    post_info['title'], 
                    content, 
                    comment_style
                )
                
                success = self.write_comment(comment)
                return success, comment
            
            return False, "본문을 가져올 수 없습니다"
            
        except Exception as e:
            return False, f"포스트 처리 중 오류: {str(e)}"

    def get_post_content(self):
        """포스트 본문 가져오기"""
        try:
            # 여러 가능한 본문 셀렉터 시도
            content_selectors = [
                ".se-main-container",  # 스마트에디터
                ".view_content",       # 구버전
                "#postViewArea",       # 구버전
                ".post-view"           # 모바일
            ]
            
            for selector in content_selectors:
                try:
                    iframe = self.driver.find_elements(By.TAG_NAME, "iframe")
                    if iframe:
                        # iframe 내부 접근
                        self.driver.switch_to.frame(iframe[0])
                        
                    content_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    content = content_element.text
                    
                    # iframe에서 나오기
                    self.driver.switch_to.default_content()
                    
                    if content:
                        return content[:1000]  # 처음 1000자만
                except:
                    self.driver.switch_to.default_content()
                    continue
                    
            return ""
            
        except Exception as e:
            print(f"본문 가져오기 실패: {e}")
            return ""

    def simulate_reading(self):
        """포스트 읽기 시뮬레이션 (스크롤)"""
        try:
            # 전체 페이지 높이 가져오기
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # 현재 위치
            current_position = 0
            
            # 랜덤하게 스크롤
            while current_position < total_height * 0.8:
                # 스크롤 거리 (100-300px)
                scroll_distance = random.randint(100, 300)
                
                # 스크롤 실행
                self.driver.execute_script(f"window.scrollBy(0, {scroll_distance})")
                current_position += scroll_distance
                
                # 읽는 시간 시뮬레이션
                time.sleep(random.uniform(0.5, 2))
                
                # 가끔 멈춰서 읽기
                if random.random() < 0.3:
                    time.sleep(random.uniform(2, 4))
                    
        except Exception as e:
            print(f"스크롤 시뮬레이션 실패: {e}")

    def click_like(self):
        """좋아요 버튼 클릭"""
        try:
            # 좋아요 버튼 찾기
            like_selectors = [
                ".u_ico_like",
                ".btn_like",
                ".like_on",
                "#area_like_btn"
            ]
            
            for selector in like_selectors:
                try:
                    like_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if like_btn and like_btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", like_btn)
                        time.sleep(1)
                        return True
                except:
                    continue
                    
            return False
            
        except Exception as e:
            print(f"좋아요 클릭 실패: {e}")
            return False

    def write_comment(self, comment_text):
        """댓글 작성"""
        try:
            # 댓글 입력 영역 찾기
            comment_selectors = [
                ".u_cbox_text",
                "#naverComment_text",
                ".comment_text"
            ]
            
            for selector in comment_selectors:
                try:
                    comment_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if comment_input:
                        # 댓글창 클릭
                        comment_input.click()
                        time.sleep(1)
                        
                        # 댓글 입력
                        comment_input.clear()
                        comment_input.send_keys(comment_text)
                        time.sleep(1)
                        
                        # 등록 버튼 찾기
                        submit_btns = [
                            ".u_cbox_btn_upload",
                            ".btn_register",
                            ".CommentWriter__submit"
                        ]
                        
                        for btn_selector in submit_btns:
                            try:
                                submit_btn = self.driver.find_element(By.CSS_SELECTOR, btn_selector)
                                if submit_btn:
                                    self.driver.execute_script("arguments[0].click();", submit_btn)
                                    time.sleep(2)
                                    return True
                            except:
                                continue
                                
                except:
                    continue
                    
            return False
            
        except Exception as e:
            print(f"댓글 작성 실패: {e}")
            return False

    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()


class ClaudeCommentGenerator:
    """Claude API를 이용한 댓글 생성"""

    def __init__(self, api_key):
        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.api_key = api_key
        except ImportError:
            raise ImportError(
                "anthropic 패키지가 설치되지 않았습니다. 'pip install anthropic'으로 설치해주세요."
            )

    def generate_comment(self, post_title, post_content, style="친근함"):
        """포스트 내용을 바탕으로 자연스러운 댓글 생성"""

        style_map = {
            "친근함": "친근하고 따뜻한 톤으로",
            "전문적": "전문적이고 정중한 톤으로",
            "캐주얼": "편안하고 자연스러운 톤으로",
            "응원": "격려하고 응원하는 톤으로",
        }

        tone = style_map.get(style, "자연스러운 톤으로")

        prompt = f"""
다음 블로그 포스트에 대해 {tone} 댓글을 작성해주세요.

포스트 제목: {post_title}
포스트 내용 일부: {post_content[:300]}

댓글 작성 가이드라인:
1. 1-2문장으로 간결하게 작성
2. 포스트 내용과 관련된 구체적인 반응
3. 자연스럽고 진정성 있게
4. 광고나 홍보성 내용 금지
5. 이모지 1-2개 정도 사용 가능
6. 한국어로 작성

댓글만 작성해주세요:"""

        try:
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )

            comment = response.content[0].text.strip()
            # 댓글이 너무 길면 자르기
            if len(comment) > 100:
                comment = comment[:97] + "..."

            return comment

        except Exception as e:
            print(f"댓글 생성 실패: {e}")
            # 기본 댓글 반환
            fallback_comments = [
                "좋은 글 잘 읽었습니다! 😊",
                "유익한 정보 감사해요 👍",
                "정말 도움이 되는 내용이네요!",
                "좋은 글 공유해주셔서 감사합니다 ✨",
            ]
            return random.choice(fallback_comments)


class BlogManagerGUI:
    """메인 GUI 클래스"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("네이버 블로그 자동 이웃관리 v1.0.0")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # 보안 매니저 초기화
        self.security_manager = FirestoreSecurityManager()
        self.is_licensed = False
        self.license_info = None
        self.current_license_key = None
        
        # 자동화 객체
        self.automation = None
        self.is_running = False
        self.processed_posts = set()  # 이미 처리한 포스트 추적

        self.setup_gui()
        self.check_saved_license()

    def setup_gui(self):
        """GUI 구성"""
        # 스타일 설정
        style = ttk.Style()
        style.theme_use("clam")

        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 제목
        title_label = ttk.Label(
            main_frame, text="네이버 블로그 자동 이웃관리", font=("Arial", 16, "bold")
        )
        title_label.pack(pady=(0, 20))

        # 라이선스 프레임
        license_frame = ttk.LabelFrame(main_frame, text="라이선스 인증", padding="15")
        license_frame.pack(fill=tk.X, pady=(0, 15))

        # 라이선스 키 입력
        license_input_frame = ttk.Frame(license_frame)
        license_input_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(license_input_frame, text="라이선스 키:").pack(anchor=tk.W)

        license_entry_frame = ttk.Frame(license_input_frame)
        license_entry_frame.pack(fill=tk.X, pady=(5, 0))

        self.license_entry = ttk.Entry(license_entry_frame, font=("Consolas", 10))
        self.license_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.verify_btn = ttk.Button(
            license_entry_frame, text="인증", command=self.verify_license
        )
        self.verify_btn.pack(side=tk.RIGHT)

        # 라이선스 상태
        self.license_status = ttk.Label(
            license_frame, text="라이선스를 입력하고 인증해주세요.", foreground="gray"
        )
        self.license_status.pack(anchor=tk.W, pady=(10, 0))

        # 하드웨어 ID 표시
        hardware_id = self.security_manager.get_hardware_id()
        hardware_frame = ttk.Frame(license_frame)
        hardware_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(hardware_frame, text="하드웨어 ID:", font=("Arial", 8)).pack(
            anchor=tk.W
        )
        hardware_id_label = ttk.Label(
            hardware_frame,
            text=hardware_id[:16] + "...",
            font=("Consolas", 8),
            foreground="gray",
        )
        hardware_id_label.pack(anchor=tk.W)

        # 네이버 로그인 프레임
        self.login_frame = ttk.LabelFrame(main_frame, text="네이버 계정", padding="15")
        self.login_frame.pack(fill=tk.X, pady=(0, 15))

        login_grid = ttk.Frame(self.login_frame)
        login_grid.pack(fill=tk.X)

        ttk.Label(login_grid, text="아이디:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.naver_id_entry = ttk.Entry(login_grid, width=25)
        self.naver_id_entry.grid(row=0, column=1, padx=(10, 20), pady=5, sticky=tk.W)

        ttk.Label(login_grid, text="비밀번호:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )
        self.naver_pw_entry = ttk.Entry(login_grid, width=25, show="*")
        self.naver_pw_entry.grid(row=1, column=1, padx=(10, 20), pady=5, sticky=tk.W)

        self.login_btn = ttk.Button(
            login_grid, text="로그인 테스트", command=self.test_naver_login
        )
        self.login_btn.grid(row=0, column=2, rowspan=2, padx=(20, 0), pady=5)

        self.login_status = ttk.Label(self.login_frame, text="", font=("Arial", 9))
        self.login_status.pack(anchor=tk.W, pady=(10, 0))

        # 자동화 설정 프레임
        self.automation_frame = ttk.LabelFrame(
            main_frame, text="자동화 설정", padding="15"
        )
        self.automation_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # 설정 옵션들
        settings_frame = ttk.Frame(self.automation_frame)
        settings_frame.pack(fill=tk.X, pady=(10, 0))

        # 댓글 스타일
        style_frame = ttk.Frame(settings_frame)
        style_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(style_frame, text="댓글 스타일:").pack(side=tk.LEFT)
        self.comment_style = ttk.Combobox(
            style_frame,
            values=["친근함", "전문적", "캐주얼", "응원"],
            state="readonly",
            width=15,
        )
        self.comment_style.pack(side=tk.LEFT, padx=(10, 20))
        self.comment_style.set("친근함")

        # 처리 설정
        ttk.Label(style_frame, text="포스트당 대기시간:").pack(side=tk.LEFT)
        self.delay_min = ttk.Spinbox(style_frame, from_=30, to=300, width=8, value=60)
        self.delay_min.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(style_frame, text="~").pack(side=tk.LEFT)
        self.delay_max = ttk.Spinbox(style_frame, from_=60, to=600, width=8, value=120)
        self.delay_max.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(style_frame, text="초").pack(side=tk.LEFT)

        # 일일 한도
        limit_frame = ttk.Frame(settings_frame)
        limit_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(limit_frame, text="일일 댓글 한도:").pack(side=tk.LEFT)
        self.daily_limit = ttk.Spinbox(limit_frame, from_=1, to=50, width=10, value=20)
        self.daily_limit.pack(side=tk.LEFT, padx=(10, 5))
        ttk.Label(limit_frame, text="개").pack(side=tk.LEFT)

        # 통계 표시
        stats_frame = ttk.Frame(self.automation_frame)
        stats_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.stats_label = ttk.Label(stats_frame, text="오늘 처리: 0 / 0", font=("Arial", 10, "bold"))
        self.stats_label.pack(side=tk.LEFT)

        # 실행 버튼들
        button_frame = ttk.Frame(self.automation_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        self.start_btn = ttk.Button(
            button_frame,
            text="자동 이웃관리 시작",
            command=self.start_automation,
            style="Accent.TButton",
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(
            button_frame, text="중지", command=self.stop_automation, state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        # 진행 상황
        progress_frame = ttk.Frame(self.automation_frame)
        progress_frame.pack(fill=tk.X, pady=(20, 10))

        ttk.Label(progress_frame, text="진행 상황:").pack(anchor=tk.W)
        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(5, 0))

        # 로그 출력 영역
        log_frame = ttk.LabelFrame(main_frame, text="실행 로그", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)

           self.log_text = scrolledtext.ScrolledText(
            log_frame, height=12, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 초기 상태 설정
        self.set_gui_state(False)

        # 시작 메시지
        self.log_message("프로그램이 시작되었습니다.")
        self.log_message(f"하드웨어 ID: {hardware_id}")

    def set_gui_state(self, enabled):
        """GUI 활성화/비활성화"""
        state = tk.NORMAL if enabled else tk.DISABLED

        widgets = [
            self.naver_id_entry,
            self.naver_pw_entry,
            self.login_btn,
            self.comment_style,
            self.delay_min,
            self.delay_max,
            self.daily_limit,
            self.start_btn,
        ]

        for widget in widgets:
            widget.config(state=state)

    def log_message(self, message):
        """로그 메시지 출력"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()

    def check_saved_license(self):
        """저장된 라이선스 확인"""
        try:
            if os.path.exists("license.dat"):
                with open("license.dat", "r") as f:
                    license_key = f.read().strip()
                    if license_key:
                        self.license_entry.insert(0, license_key)
                        self.log_message("저장된 라이선스를 불러왔습니다.")
                        # 자동으로 라이선스 검증
                        self.root.after(1000, self.verify_license)
        except Exception as e:
            self.log_message(f"라이선스 불러오기 실패: {e}")

    def verify_license(self):
        """라이선스 검증"""
        license_key = self.license_entry.get().strip()
        if not license_key:
            self.license_status.config(
                text="라이선스 키를 입력해주세요.", foreground="red"
            )
            return

        self.log_message("라이선스 검증 중...")
        self.verify_btn.config(state=tk.DISABLED, text="검증 중...")

        # 별도 스레드에서 검증
        threading.Thread(
            target=self._verify_license_thread, args=(license_key,), daemon=True
        ).start()

    def _verify_license_thread(self, license_key):
        """라이선스 검증 스레드"""
        try:
            success, result = self.security_manager.verify_license_online(license_key)

            # UI 업데이트는 메인 스레드에서
            self.root.after(
                0, self._handle_license_result, success, result, license_key
            )

        except Exception as e:
            self.root.after(
                0, self._handle_license_result, False, f"검증 중 오류: {e}", license_key
            )

    def _handle_license_result(self, success, result, license_key):
        """라이선스 검증 결과 처리"""
        self.verify_btn.config(state=tk.NORMAL, text="인증")

        if success:
            self.is_licensed = True
            self.license_info = result
            self.current_license_key = license_key

            # 만료일 계산
            expire_date_str = result.get("expire_date")
            if expire_date_str:
                expire_date = datetime.fromisoformat(expire_date_str)
                days_left = (expire_date - datetime.now()).days
                expire_text = f"({days_left}일 남음)" if days_left > 0 else "(만료됨)"
            else:
                expire_text = "(무제한)"

            customer_id = result.get("customer_id", "Unknown")

            self.license_status.config(
                text=f"✓ 라이선스 인증 완료 {expire_text} - {customer_id}",
                foreground="green",
            )

            self.set_gui_state(True)
            self.log_message(f"라이선스 인증 성공: {customer_id}")

            # 라이선스 키 저장
            try:
                with open("license.dat", "w") as f:
                    f.write(license_key)
            except:
                pass

        else:
            self.is_licensed = False
            self.license_status.config(text=f"✗ {result}", foreground="red")
            self.set_gui_state(False)
            self.log_message(f"라이선스 인증 실패: {result}")

    def test_naver_login(self):
        """네이버 로그인 테스트"""
        if not self.is_licensed:
            messagebox.showerror("오류", "먼저 라이선스를 인증해주세요.")
            return

        user_id = self.naver_id_entry.get().strip()
        password = self.naver_pw_entry.get().strip()

        if not user_id or not password:
            messagebox.showerror("오류", "아이디와 비밀번호를 입력해주세요.")
            return

        self.login_status.config(text="로그인 테스트 중...", foreground="orange")
        self.log_message("네이버 로그인 테스트 시작...")

        # 별도 스레드에서 실행
        threading.Thread(
            target=self._test_login_thread, args=(user_id, password), daemon=True
        ).start()

    def _test_login_thread(self, user_id, password):
        """로그인 테스트 스레드"""
        try:
            # 자동화 객체 생성
            test_automation = NaverBlogAutomation(headless=True)
            
            if test_automation.setup_driver():
                success, message = test_automation.login_naver(user_id, password)
                test_automation.close()
                
                # UI 업데이트
                self.root.after(0, self._handle_login_result, success, message)
            else:
                self.root.after(0, self._handle_login_result, False, "드라이버 설정 실패")
                
        except Exception as e:
            self.root.after(0, self._handle_login_result, False, f"테스트 실패: {str(e)}")

    def _handle_login_result(self, success, message):
        """로그인 결과 처리"""
        if success:
            self.login_status.config(text="✓ 로그인 테스트 성공", foreground="green")
            self.log_message("네이버 로그인 테스트 성공")
        else:
            self.login_status.config(text=f"✗ {message}", foreground="red")
            self.log_message(f"로그인 테스트 실패: {message}")

    def start_automation(self):
        """자동화 시작"""
        if not self.is_licensed:
            messagebox.showerror("오류", "라이선스를 인증해주세요.")
            return

        user_id = self.naver_id_entry.get().strip()
        password = self.naver_pw_entry.get().strip()

        if not user_id or not password:
            messagebox.showerror("오류", "네이버 계정 정보를 입력해주세요.")
            return

        self.is_running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()

        # 통계 초기화
        self.today_count = 0
        self.update_stats()

        self.log_message("자동 이웃관리를 시작합니다...")

        # 실제 자동화 로직은 별도 스레드에서 실행
        threading.Thread(
            target=self._automation_thread, args=(user_id, password), daemon=True
        ).start()

    def _automation_thread(self, user_id, password):
        """자동화 실행 스레드"""
        try:
            # 자동화 객체 생성
            self.automation = NaverBlogAutomation(headless=False)
            
            # 드라이버 설정
            if not self.automation.setup_driver():
                self.root.after(0, self.log_message, "드라이버 설정 실패")
                return
            
            # 로그인
            self.root.after(0, self.log_message, "네이버 로그인 중...")
            success, message = self.automation.login_naver(user_id, password)
            
            if not success:
                self.root.after(0, self.log_message, f"로그인 실패: {message}")
                return
            
            self.root.after(0, self.log_message, "로그인 성공!")
            
            # 일일 한도
            daily_limit = int(self.daily_limit.get())
            
            # 메인 루프
            while self.is_running and self.today_count < daily_limit:
                try:
                    # 이웃 새글 가져오기
                    self.root.after(0, self.log_message, "이웃 새글 확인 중...")
                    posts = self.automation.get_neighbor_new_posts()
                    
                    if not posts:
                        self.root.after(0, self.log_message, "새 글이 없습니다. 5분 후 다시 확인합니다.")
                        for _ in range(300):  # 5분 대기
                            if not self.is_running:
                                break
                            time.sleep(1)
                        continue
                    
                    # 새 포스트 처리
                    for post in posts:
                        if not self.is_running or self.today_count >= daily_limit:
                            break
                        
                        # 이미 처리한 포스트는 건너뛰기
                        if post['url'] in self.processed_posts:
                            continue
                        
                        self.root.after(
                            0, 
                            self.log_message, 
                            f"포스트 처리 중: [{post['blogger']}] {post['title'][:30]}..."
                        )
                        
                        # 포스트 처리
                        success, comment = self.automation.process_post(
                            post, 
                            self.comment_style.get()
                        )
                        
                        if success:
                            self.processed_posts.add(post['url'])
                            self.today_count += 1
                            self.root.after(0, self.update_stats)
                            self.root.after(
                                0, 
                                self.log_message, 
                                f"✓ 댓글 작성 완료: {comment[:50]}..."
                            )
                        else:
                            self.root.after(
                                0, 
                                self.log_message, 
                                f"✗ 댓글 작성 실패: {comment}"
                            )
                        
                        # 다음 포스트 처리 전 대기
                        delay = random.uniform(
                            int(self.delay_min.get()), 
                            int(self.delay_max.get())
                        )
                        self.root.after(
                            0, 
                            self.log_message, 
                            f"다음 포스트까지 {int(delay)}초 대기..."
                        )
                        
                        for _ in range(int(delay)):
                            if not self.is_running:
                                break
                            time.sleep(1)
                    
                    # 다음 확인까지 대기
                    if self.is_running and self.today_count < daily_limit:
                        self.root.after(0, self.log_message, "10분 후 새 글을 확인합니다.")
                        for _ in range(600):  # 10분 대기
                            if not self.is_running:
                                break
                            time.sleep(1)
                    
                except Exception as e:
                    self.root.after(0, self.log_message, f"오류 발생: {str(e)}")
                    time.sleep(60)  # 오류 시 1분 대기
            
            if self.today_count >= daily_limit:
                self.root.after(0, self.log_message, f"일일 한도 {daily_limit}개 도달!")
            
        except Exception as e:
            self.root.after(0, self.log_message, f"자동화 오류: {str(e)}")
        
        finally:
            if self.automation:
                self.automation.close()
            self.root.after(0, self._reset_automation_ui)

    def update_stats(self):
        """통계 업데이트"""
        daily_limit = int(self.daily_limit.get())
        self.stats_label.config(text=f"오늘 처리: {self.today_count} / {daily_limit}")

    def _reset_automation_ui(self):
        """자동화 UI 리셋"""
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self.is_running = False
        self.log_message("자동화가 중지되었습니다.")

    def stop_automation(self):
        """자동화 중지"""
        self.is_running = False
        self.log_message("자동화 중지 요청...")

    def on_closing(self):
        """프로그램 종료 시 처리"""
        self.is_running = False
        if self.automation:
            self.automation.close()
        self.root.destroy()

    def run(self):
        """프로그램 실행"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


# Firestore 라이선스 생성 도구 (관리자용)
def create_license_in_firestore(license_key, customer_id, days=30, features=None):
    """Firestore에 새 라이선스 생성"""
    if features is None:
        features = ["blog_management", "auto_comment", "auto_like"]

    try:
        # Firebase 초기화
        if not firebase_admin._apps:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)

        db = firestore.client()

        # 라이선스 데이터
        expire_date = datetime.now() + timedelta(days=days) if days > 0 else None

        license_data = {
            "customer_id": customer_id,
            "active": True,
            "created_date": datetime.now().isoformat(),
            "expire_date": expire_date.isoformat() if expire_date else None,
            "features": features,
            "max_devices": 1,
            "hardware_id": None,  # 첫 사용 시 등록됨
            "first_used": None,
            "last_used": None,
            "usage_count": 0,
        }

        # Firestore에 저장
        db.collection("licenses").document(license_key).set(license_data)

        print(f"✓ 라이선스 생성 완료")
        print(f"  - 라이선스 키: {license_key}")
        print(f"  - 고객 ID: {customer_id}")
        print(f"  - 유효 기간: {days}일" if days > 0 else "  - 유효 기간: 무제한")
        print(f"  - 기능: {', '.join(features)}")

        return True

    except Exception as e:
        print(f"라이선스 생성 실패: {e}")
        return False


def admin_menu():
    """관리자 메뉴"""
    while True:
        print("\n" + "=" * 50)
        print("관리자 도구")
        print("=" * 50)
        print("1. 라이선스 생성")
        print("2. 프로그램 실행")
        print("0. 종료")
        print("-" * 50)

        choice = input("선택: ").strip()

        if choice == "1":
            # 라이선스 생성
            print("\n라이선스 생성")
            license_key = input("라이선스 키 (비워두면 자동 생성): ").strip()
            if not license_key:
                import secrets
                license_key = secrets.token_urlsafe(16)
                
            customer_id = input("고객 ID: ").strip()
            days = int(input("유효 기간 (일, 0=무제한): ") or "30")
            
            create_license_in_firestore(license_key, customer_id, days)
            
        elif choice == "2":
            app = BlogManagerGUI()
            app.run()
            break
            
        elif choice == "0":
            break


# 메인 실행
if __name__ == "__main__":
    import sys

    # Claude API 키 설정 (.env 파일 또는 하드코딩)
    if not os.getenv('ANTHROPIC_API_KEY'):
        # 여기에 실제 API 키를 입력하세요
        os.environ['ANTHROPIC_API_KEY'] = "sk-ant-api03-YOUR-API-KEY-HERE"

    # 명령행 인수로 관리자 모드 실행
    if len(sys.argv) > 1 and sys.argv[1] == "--admin":
        admin_menu()
    else:
        # 일반 사용자 모드
        app = BlogManagerGUI()
        app.run()