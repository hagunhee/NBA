"""
네이버 블로그 댓글 작성자 ID 추출기
특정 포스팅의 모든 댓글 작성자 아이디를 추출하여 텍스트 파일로 저장
"""

import time
import random
import os
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def setup_driver(headless=False):
    """Chrome 드라이버 설정"""
    try:
        print("브라우저 초기화 중...")

        # Chrome 옵션 설정
        options = Options()

        # 기본 옵션들
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")

        # ChromeDriverManager로 자동 설치
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # 자동화 탐지 방지
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        print("✓ 브라우저 초기화 완료")
        return driver

    except Exception as e:
        print(f"✗ 브라우저 초기화 실패: {e}")
        return None


class CommentExtractor:
    """네이버 블로그 댓글 작성자 ID 추출 클래스"""

    def __init__(self, headless=False):
        self.driver = setup_driver(headless)
        self.wait = WebDriverWait(self.driver, 20) if self.driver else None
        self.extracted_ids = set()  # 중복 제거를 위한 set

    def wait_for_page_load(self):
        """페이지가 완전히 로드될 때까지 대기"""
        try:
            print("페이지 로딩 대기 중...")

            # 1. JavaScript 실행 완료 대기
            self.driver.execute_script("return document.readyState") == "complete"

            # 2. 블로그 프레임 로딩 대기
            time.sleep(5)

            # 3. 메인 프레임으로 전환 시도
            try:
                # mainFrame이 있는지 확인
                main_frame = self.driver.find_elements(By.ID, "mainFrame")
                if main_frame:
                    print("mainFrame 발견, 프레임 전환...")
                    self.driver.switch_to.frame(main_frame[0])
                    time.sleep(3)
            except Exception as e:
                print(f"mainFrame 전환 실패 (정상일 수 있음): {e}")

            # 4. 추가 대기
            time.sleep(5)

            print("✓ 페이지 로딩 완료")
            return True
        except Exception as e:
            print(f"페이지 로딩 대기 중 오류: {e}")
            return False

    def open_comment_section(self):
        """댓글창 열기 (pcol2 -> pcol3 변환)"""
        try:
            print("2. 댓글창 열기 시도...")

            # 페이지 하단으로 스크롤 (댓글 영역 근처)
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(3)

            # 댓글창이 이미 열려있는지 확인
            comment_area_open = self.driver.find_elements(
                By.CSS_SELECTOR, ".area_comment.pcol3"
            )
            if comment_area_open:
                print("✓ 댓글창이 이미 열려있습니다.")
                return True

            # 다양한 셀렉터로 댓글 버튼 찾기
            comment_btn_selectors = [
                # 가장 일반적인 패턴들
                "a.btn_comment",
                ".btn_comment",
                "button.btn_comment",
                # ID 기반 패턴
                "a[id*='Comi']",
                "a[id*='comment']",
                "a[id*='Comment']",
                "a#btn_comment_2",  # 실제로 발견된 ID
                # 클래스 기반 패턴
                "a[class*='comment']",
                "button[class*='comment']",
                # 텍스트 기반 (JavaScript로 처리)
                "//a[contains(text(), '댓글')]",
                "//button[contains(text(), '댓글')]",
                # 속성 기반
                "a[onclick*='comment']",
                "button[onclick*='comment']",
                # 일반적인 버튼 패턴
                ".post_btn_wrap a",
                ".post_btn_wrap button",
                # 모든 a 태그 (마지막 수단)
                "a",
            ]

            print("다양한 방법으로 댓글 버튼 찾기...")

            for selector in comment_btn_selectors:
                try:
                    print(f"  - {selector} 시도 중...")

                    # XPath인 경우
                    if selector.startswith("//"):
                        buttons = self.driver.find_elements(By.XPATH, selector)
                    else:
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    print(f"    {len(buttons)}개 요소 발견")

                    for i, btn in enumerate(buttons):
                        try:
                            if not btn.is_displayed() or not btn.is_enabled():
                                continue

                            btn_text = btn.text.strip()
                            btn_id = btn.get_attribute("id") or ""
                            btn_class = btn.get_attribute("class") or ""
                            onclick = btn.get_attribute("onclick") or ""

                            # 댓글 관련 버튼인지 확인
                            if any(
                                keyword in str(attr).lower()
                                for keyword in ["comment", "댓글", "comi"]
                                for attr in [btn_text, btn_id, btn_class, onclick]
                            ):

                                print(f"    ✓ 댓글 버튼 후보 발견!")
                                print(f"      텍스트: '{btn_text}'")
                                print(f"      ID: '{btn_id}'")
                                print(f"      클래스: '{btn_class[:50]}...'")

                                # 버튼으로 스크롤
                                self.driver.execute_script(
                                    "arguments[0].scrollIntoView({block: 'center'});",
                                    btn,
                                )
                                time.sleep(2)

                                # 클릭 시도
                                try:
                                    btn.click()
                                    print("    - 일반 클릭 성공")
                                except:
                                    try:
                                        self.driver.execute_script(
                                            "arguments[0].click();", btn
                                        )
                                        print("    - JavaScript 클릭 성공")
                                    except:
                                        ActionChains(self.driver).click(btn).perform()
                                        print("    - ActionChains 클릭 성공")

                                time.sleep(5)

                                # 성공 여부 확인
                                if self.check_comment_opened():
                                    print("✓ 댓글창 열기 성공!")

                                    # 댓글 iframe이 동적으로 생성되도록 추가 대기
                                    print("댓글 iframe 생성 대기...")
                                    time.sleep(5)

                                    # 페이지 다시 스크롤 (iframe 로드 트리거)
                                    self.driver.execute_script(
                                        "window.scrollTo(0, document.body.scrollHeight);"
                                    )
                                    time.sleep(3)

                                    return True

                        except Exception as e:
                            continue

                except Exception as e:
                    continue

            # JavaScript로 직접 댓글 열기 시도
            print("\nJavaScript로 직접 댓글 열기 시도...")
            try:
                # 댓글 관련 함수 실행 시도
                js_commands = [
                    "if(typeof toggleComment !== 'undefined') toggleComment();",
                    "if(typeof openComment !== 'undefined') openComment();",
                    "if(typeof showComment !== 'undefined') showComment();",
                    "document.querySelector('.btn_comment')?.click();",
                    "document.querySelector('a[id*=\"Comi\"]')?.click();",
                    "document.getElementById('btn_comment_2')?.click();",
                ]

                for cmd in js_commands:
                    try:
                        self.driver.execute_script(cmd)
                        time.sleep(3)
                        if self.check_comment_opened():
                            print("✓ JavaScript로 댓글창 열기 성공!")
                            time.sleep(5)
                            return True
                    except:
                        continue
            except:
                pass

            print("✗ 댓글 열기 버튼을 찾을 수 없습니다.")
            return False

        except Exception as e:
            print(f"✗ 댓글창 열기 실패: {e}")
            return False

    def check_comment_opened(self):
        """댓글창이 열렸는지 확인"""
        try:
            # pcol3 클래스 확인
            if self.driver.find_elements(By.CSS_SELECTOR, ".area_comment.pcol3"):
                return True

            # iframe 생성 확인
            if self.driver.find_elements(
                By.CSS_SELECTOR, "iframe[src*='comment'], #commentIframe"
            ):
                return True

            # 댓글 영역 표시 확인
            comment_areas = self.driver.find_elements(By.CSS_SELECTOR, ".area_comment")
            for area in comment_areas:
                if area.is_displayed() and "pcol3" in area.get_attribute("class"):
                    return True

            return False
        except:
            return False

    def wait_for_comment_area_visible(self):
        """댓글 영역이 표시될 때까지 대기"""
        try:
            print("3. 댓글 영역 표시 대기 중...")

            # 댓글 영역 div 찾기 (다양한 패턴)
            comment_area_selectors = [
                "div[id^='naverComment_'][id$='_ct']",
                "div[id*='naverComment_']",
                "#naverComment_201_223887293847_ct",  # 구체적인 예시
                ".area_comment div[style*='block']",
                ".u_cbox_wrap",
                "#cbox_module",
            ]

            wait_long = WebDriverWait(self.driver, 30)

            for selector in comment_area_selectors:
                try:
                    print(f"  - {selector} 확인 중...")

                    # 요소가 표시될 때까지 대기
                    element = wait_long.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )

                    # display:block 확인
                    if element.is_displayed():
                        print(f"✓ 댓글 영역 표시 확인: {selector}")

                        # 댓글 내용이 로드될 때까지 추가 대기
                        time.sleep(3)
                        return True

                except TimeoutException:
                    print(f"  - {selector} 타임아웃")
                    continue
                except Exception as e:
                    print(f"  - {selector} 오류: {e}")
                    continue

            # JavaScript로 직접 확인
            print("\nJavaScript로 댓글 영역 확인...")
            try:
                # naverComment로 시작하는 div 찾기
                comment_divs = self.driver.execute_script(
                    """
                    var divs = document.querySelectorAll('div[id^="naverComment_"]');
                    var visibleDivs = [];
                    for (var i = 0; i < divs.length; i++) {
                        var style = window.getComputedStyle(divs[i]);
                        if (style.display !== 'none') {
                            visibleDivs.push({
                                id: divs[i].id,
                                display: style.display,
                                hasChildren: divs[i].children.length > 0
                            });
                        }
                    }
                    return visibleDivs;
                """
                )

                if comment_divs:
                    print(f"✓ 표시된 댓글 영역 발견: {comment_divs}")
                    time.sleep(3)
                    return True

            except Exception as e:
                print(f"JavaScript 확인 실패: {e}")

            print("✗ 댓글 영역을 찾을 수 없습니다.")
            return False

        except Exception as e:
            print(f"✗ 댓글 영역 대기 실패: {e}")
            return False

    def wait_for_comments_load(self):
        """댓글 로딩 대기"""
        try:
            print("4. 댓글 로딩 대기 중...")

            wait_long = WebDriverWait(self.driver, 30)

            # 댓글 요소 셀렉터들
            comment_selectors = [
                ".u_cbox_comment",
                "li.u_cbox_comment",
                ".cbox_module",
                ".u_cbox_area",
                "div[class*='comment']",
                ".CommentBox",
                ".comment_area",
            ]

            for selector in comment_selectors:
                try:
                    elements = wait_long.until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if elements:
                        print(f"✓ 댓글 영역 발견: {selector} ({len(elements)}개)")
                        time.sleep(2)
                        return True
                except TimeoutException:
                    continue
                except Exception:
                    continue

            print("⚠️ 댓글을 찾을 수 없습니다. 댓글이 없는 포스트일 수 있습니다.")
            return False

        except Exception as e:
            print(f"✗ 댓글 로딩 대기 실패: {e}")
            return False

    def extract_author_id_from_link(self, link):
        """링크에서 작성자 ID 추출"""
        href = link.get_attribute("href")

        if href:
            # blog.naver.com/username 패턴
            if "blog.naver.com" in href:
                return href.split("/")[-1].split("?")[0]

            # PostView.naver?blogId=username 패턴
            if "PostView.naver" in href and "blogId=" in href:
                return href.split("blogId=")[1].split("&")[0]

        # href에서 추출 실패 시 텍스트 사용
        author_text = link.text.strip()
        if author_text:
            return author_text

        # data-log 속성에서 추출 시도
        data_log = link.get_attribute("data-log")
        if data_log and "blog_id" in data_log:
            try:
                log_data = json.loads(data_log)
                return log_data.get("blog_id")
            except:
                pass

        return None

    def extract_comment_authors(self):
        """현재 페이지의 댓글 작성자 추출"""
        try:
            # 댓글 요소 찾기
            comment_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "li.u_cbox_comment"
            )

            if not comment_elements:
                print("댓글 요소를 찾을 수 없습니다.")
                return []

            print(f"댓글 요소 발견: li.u_cbox_comment ({len(comment_elements)}개)")
            current_page_ids = []

            for i, comment in enumerate(comment_elements):
                try:
                    # data-info 속성에서 작성자 정보 추출
                    data_info = comment.get_attribute("data-info")
                    if data_info:
                        try:
                            import json

                            info_dict = json.loads(data_info)
                            author_id = info_dict.get("userIdNo")

                            if author_id and author_id not in self.extracted_ids:
                                self.extracted_ids.add(author_id)
                                current_page_ids.append(author_id)
                                print(f"  {len(current_page_ids):2d}. {author_id}")
                                continue
                        except:
                            pass

                    # data-info가 없거나 파싱 실패시 기존 방법 시도
                    # 작성자 정보 영역 찾기
                    author_id = None

                    # 방법 1: u_cbox_info 내의 a 태그에서 추출
                    try:
                        info_area = comment.find_element(
                            By.CSS_SELECTOR, ".u_cbox_info"
                        )
                        # 첫 번째 a 태그가 작성자 링크
                        author_link = info_area.find_element(By.CSS_SELECTOR, "a")
                        href = author_link.get_attribute("href")

                        if href and "blog.naver.com" in href:
                            # URL에서 ID 추출
                            # https://blog.naver.com/phss7290 형태에서 phss7290 추출
                            author_id = href.rstrip("/").split("/")[-1].split("?")[0]
                    except:
                        pass

                    # 방법 2: onclick 속성에서 추출
                    if not author_id:
                        try:
                            links = comment.find_elements(By.CSS_SELECTOR, "a[onclick]")
                            for link in links:
                                onclick = link.get_attribute("onclick")
                                if onclick and "blog.naver.com" in onclick:
                                    # onclick에서 ID 추출
                                    match = re.search(
                                        r'blog\.naver\.com/([^"\'?]+)', onclick
                                    )
                                    if match:
                                        author_id = match.group(1)
                                        break
                        except:
                            pass

                    # 방법 3: 텍스트로 표시된 ID 찾기
                    if not author_id:
                        try:
                            # u_cbox_info_main 내의 첫 번째 span이나 a 태그의 텍스트
                            info_main = comment.find_element(
                                By.CSS_SELECTOR, ".u_cbox_info_main"
                            )
                            id_element = info_main.find_element(
                                By.CSS_SELECTOR, "a, span"
                            )
                            potential_id = id_element.text.strip()
                            if potential_id and not potential_id.startswith("http"):
                                author_id = potential_id
                        except:
                            pass

                    if author_id and author_id not in self.extracted_ids:
                        self.extracted_ids.add(author_id)
                        current_page_ids.append(author_id)
                        print(f"  {len(current_page_ids):2d}. {author_id}")

                except Exception as e:
                    # 개별 댓글 처리 실패시 계속 진행
                    continue

            return current_page_ids

        except Exception as e:
            print(f"✗ 댓글 작성자 추출 실패: {e}")
            return []

    def get_current_page_number(self):
        """현재 페이지 번호 확인"""
        try:
            print("\n현재 페이지 번호 확인 중...")

            # 페이지네이션 요소 찾기
            paginate_elements = self.driver.find_elements(
                By.CSS_SELECTOR, ".u_cbox_paginate"
            )
            if paginate_elements:
                print("페이지네이션 요소 발견")

                # 모든 페이지 번호 요소 찾기
                page_spans = paginate_elements[0].find_elements(
                    By.CSS_SELECTOR, "span.u_cbox_num_page"
                )
                page_links = paginate_elements[0].find_elements(
                    By.CSS_SELECTOR, "a.u_cbox_page"
                )

                # a 태그의 텍스트 목록 생성
                link_texts = []
                for link in page_links:
                    text = link.text.strip()
                    if text.isdigit():
                        link_texts.append(text)

                # span 태그 중에서 a 태그와 쌍을 이루지 않는 것이 현재 페이지
                for span in page_spans:
                    text = span.text.strip()
                    if text.isdigit() and text not in link_texts:
                        # 부모 요소가 a 태그가 아닌지 확인
                        parent = span.find_element(By.XPATH, "..")
                        if parent.tag_name != "a":
                            current_page = int(text)
                            print(f"✓ 현재 페이지: {current_page} (클릭 불가능한 span)")
                            return current_page

                # 위 방법이 실패하면 u_cbox_page_on 클래스 찾기
                on_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, ".u_cbox_paginate .u_cbox_page_on"
                )
                if on_elements:
                    text = on_elements[0].text.strip()
                    if text.isdigit():
                        current_page = int(text)
                        print(f"✓ 현재 페이지: {current_page} (u_cbox_page_on)")
                        return current_page

                # 그래도 못 찾으면 모든 요소 디버깅 출력
                all_elements = paginate_elements[0].find_elements(
                    By.CSS_SELECTOR, "a, span"
                )
                for i, elem in enumerate(all_elements):
                    try:
                        text = elem.text.strip()
                        tag = elem.tag_name
                        classes = elem.get_attribute("class") or ""
                        parent_tag = elem.find_element(By.XPATH, "..").tag_name
                        if text and text.isdigit():
                            print(
                                f"  요소 {i}: <{tag}> '{text}' class='{classes}' parent=<{parent_tag}>"
                            )
                    except:
                        continue

            print("현재 페이지 번호를 확인할 수 없습니다. 기본값 1 사용")
            return 1

        except Exception as e:
            print(f"현재 페이지 번호 확인 실패: {e}")
            return 1

    def get_total_pages(self):
        """총 페이지 수 확인"""
        try:
            print("\n총 페이지 수 확인 중...")

            # 페이지네이션에서 마지막 페이지 번호 찾기
            page_selectors = [
                ".u_cbox_paginate a:not(.u_cbox_page_prev):not(.u_cbox_page_next)",
                ".u_cbox_paginate a",
                ".u_cbox_paginate span",
                ".u_cbox_paginate strong",
                ".paginate a",
                ".paging a",
            ]

            max_page = 1
            page_numbers = []

            for selector in page_selectors:
                try:
                    page_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in page_elements:
                        try:
                            page_text = element.text.strip()
                            # 숫자만 있는 텍스트인지 확인
                            if page_text.isdigit():
                                page_num = int(page_text)
                                page_numbers.append(page_num)
                                max_page = max(max_page, page_num)
                        except:
                            continue
                except:
                    continue

            # 찾은 모든 페이지 번호 출력 (디버깅용)
            if page_numbers:
                print(f"발견된 페이지 번호들: {sorted(set(page_numbers))}")

            # "다음" 버튼이 있는지 확인하여 추가 페이지가 있는지 체크
            try:
                next_buttons = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".u_cbox_page_next:not(.u_cbox_page_disabled), .u_cbox_paginate .next:not(.disabled)",
                )
                if next_buttons and len(next_buttons) > 0:
                    print("다음 페이지 버튼이 활성화되어 있음 - 추가 페이지 존재")
                    # 현재 보이는 최대 페이지보다 더 많은 페이지가 있을 수 있음
            except:
                pass

            print(f"총 페이지 수: {max_page}")
            return max_page

        except Exception as e:
            print(f"페이지 수 확인 실패: {e}, 기본값 1 사용")
            return 1
        """총 페이지 수 확인"""
        try:
            # 페이지네이션 찾기
            page_selectors = [
                ".u_cbox_paginate a:not(.u_cbox_page_prev):not(.u_cbox_page_next)",
                ".paginate a",
                "a[onclick*='page']",
                ".paging a",
            ]

            max_page = 1

            for selector in page_selectors:
                try:
                    page_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in page_elements:
                        try:
                            page_text = element.text.strip()
                            if page_text.isdigit():
                                page_num = int(page_text)
                                max_page = max(max_page, page_num)
                        except:
                            continue

                    if max_page > 1:
                        break

                except:
                    continue

            print(f"총 페이지 수: {max_page}")
            return max_page

        except Exception as e:
            print(f"페이지 수 확인 실패: {e}, 기본값 1 사용")
            return 1

    def go_to_all_pages_and_get_total(self):
        """모든 페이지를 순회하면서 실제 총 페이지 수 확인"""
        try:
            print("\n전체 페이지 확인을 위해 마지막 페이지로 이동 중...")

            current_page = self.get_current_page_number()
            max_page = current_page

            # 다음 페이지 버튼을 계속 클릭하여 마지막 페이지까지 이동
            while True:
                try:
                    # 다음 페이지 버튼 찾기
                    next_btn = None
                    next_selectors = [
                        ".u_cbox_page_next:not(.u_cbox_page_disabled)",
                        ".u_cbox_paginate .next:not(.disabled)",
                        "a.u_cbox_page_next",
                        ".paginate .next",
                    ]

                    for selector in next_selectors:
                        try:
                            buttons = self.driver.find_elements(
                                By.CSS_SELECTOR, selector
                            )
                            for btn in buttons:
                                if btn.is_displayed() and btn.is_enabled():
                                    # disabled 클래스가 없는지 확인
                                    btn_class = btn.get_attribute("class") or ""
                                    if "disabled" not in btn_class:
                                        next_btn = btn
                                        break
                            if next_btn:
                                break
                        except:
                            continue

                    if not next_btn:
                        print(f"마지막 페이지 도달. 총 페이지: {max_page}")
                        break

                    # 다음 페이지로 이동
                    self.driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(2)

                    # 새 페이지 번호 확인
                    new_page = self.get_current_page_number()
                    if new_page > max_page:
                        max_page = new_page
                    else:
                        # 페이지가 증가하지 않으면 마지막 페이지
                        break

                except Exception as e:
                    print(f"페이지 이동 중 오류: {e}")
                    break

            return max_page

        except Exception as e:
            print(f"전체 페이지 확인 실패: {e}")
            return self.get_total_pages()  # 기본 방식으로 폴백

    def go_to_specific_page(self, page_num):
        """특정 페이지로 이동"""
        try:
            print(f"페이지 {page_num}로 이동 중...")

            # 현재 페이지가 목표 페이지와 같으면 이동 불필요
            current = self.get_current_page_number()
            if current == page_num:
                print(f"이미 {page_num}페이지에 있습니다.")
                return True

            # 페이지네이션 요소 찾기
            paginate = self.driver.find_element(By.CSS_SELECTOR, ".u_cbox_paginate")

            # 페이지 번호에 해당하는 a.u_cbox_page 찾기
            page_links = paginate.find_elements(By.CSS_SELECTOR, "a.u_cbox_page")

            for link in page_links:
                try:
                    link_text = link.text.strip()
                    if link_text == str(page_num):
                        print(f"페이지 {page_num} 링크 발견")

                        # 요소가 보이도록 스크롤
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", link
                        )
                        time.sleep(1)

                        # 클릭 전 현재 댓글 수 저장 (변화 감지용)
                        before_comments = len(
                            self.driver.find_elements(
                                By.CSS_SELECTOR, "li.u_cbox_comment"
                            )
                        )

                        # 여러 방법으로 클릭 시도
                        click_success = False

                        # 방법 1: JavaScript 클릭
                        try:
                            self.driver.execute_script("arguments[0].click();", link)
                            click_success = True
                            print("JavaScript 클릭 실행")
                        except:
                            # 방법 2: 일반 클릭
                            try:
                                link.click()
                                click_success = True
                                print("일반 클릭 실행")
                            except:
                                # 방법 3: ActionChains
                                try:
                                    ActionChains(self.driver).move_to_element(
                                        link
                                    ).click().perform()
                                    click_success = True
                                    print("ActionChains 클릭 실행")
                                except:
                                    pass

                        if click_success:
                            # 페이지 변화 대기
                            print("페이지 로딩 대기 중...")

                            # 방법 1: 댓글 수 변화 대기
                            wait = WebDriverWait(self.driver, 10)
                            try:
                                wait.until(
                                    lambda driver: len(
                                        driver.find_elements(
                                            By.CSS_SELECTOR, "li.u_cbox_comment"
                                        )
                                    )
                                    != before_comments
                                )
                                print("댓글 목록이 변경됨")
                            except TimeoutException:
                                print("댓글 목록 변경 대기 시간 초과")

                            # 추가 대기
                            time.sleep(2)

                            # 현재 페이지 다시 확인
                            new_current = self.get_current_page_number()
                            if new_current == page_num:
                                print(f"✓ 페이지 {page_num} 이동 성공")
                                return True
                            else:
                                print(
                                    f"페이지 이동 실패: 현재 {new_current}페이지 (목표: {page_num})"
                                )

                        break

                except Exception as e:
                    print(f"링크 클릭 중 오류: {e}")
                    continue

            # onclick 속성으로 시도
            print("onclick 속성으로 페이지 이동 시도...")
            onclick_links = self.driver.find_elements(
                By.CSS_SELECTOR, "a[onclick*='page']"
            )
            for link in onclick_links:
                try:
                    onclick = link.get_attribute("onclick") or ""
                    # page(2) 또는 page=2 형식 확인
                    if f"page({page_num})" in onclick or f"page={page_num}" in onclick:
                        print(f"onclick 링크 발견: {onclick}")
                        self.driver.execute_script("arguments[0].click();", link)
                        time.sleep(3)

                        new_current = self.get_current_page_number()
                        if new_current == page_num:
                            print(f"✓ onclick으로 페이지 {page_num} 이동 성공")
                            return True
                except:
                    continue

            print(f"페이지 {page_num} 이동 실패")
            return False

        except Exception as e:
            print(f"페이지 {page_num} 이동 중 오류: {e}")
            return False

    def click_prev_page(self):
        """이전 페이지로 이동"""
        try:
            prev_selectors = [
                ".u_cbox_page_prev:not(.u_cbox_page_disabled)",
                "a[class*='prev']:not([class*='disabled'])",
                ".paginate .prev",
                "a[title='이전']",
            ]

            for selector in prev_selectors:
                try:
                    prev_buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for prev_btn in prev_buttons:
                        if prev_btn.is_displayed() and prev_btn.is_enabled():
                            self.driver.execute_script(
                                "arguments[0].click();", prev_btn
                            )
                            time.sleep(random.uniform(2, 4))
                            return True
                except:
                    continue

            print("이전 페이지 버튼을 찾을 수 없습니다.")
            return False

        except Exception as e:
            print(f"✗ 이전 페이지 이동 실패: {e}")
            return False

    def extract_all_comments(self, post_url):
        """모든 댓글 페이지를 순회하며 작성자 ID 추출"""
        try:
            if not self.driver:
                print("✗ 브라우저가 초기화되지 않았습니다.")
                return False

            print(f"\n{'='*60}")
            print(f"댓글 추출 시작: {post_url}")
            print(f"{'='*60}")

            # 1. 포스트 페이지 방문
            print("1. 포스트 페이지 접속 중...")
            self.driver.get(post_url)

            # 페이지 완전 로딩 대기
            self.wait_for_page_load()

            # 2. 댓글창 열기
            if not self.open_comment_section():
                print("✗ 댓글창을 열 수 없습니다.")
                return False

            # 3. 댓글 영역이 표시될 때까지 대기 (iframe 대신)
            if not self.wait_for_comment_area_visible():
                print("댓글 영역이 표시되지 않습니다. iframe 방식 시도...")
                # 일부 블로그는 여전히 iframe을 사용할 수 있으므로 폴백
                if not self.switch_to_comment_frame():
                    return False

            # 4. 댓글 로딩 대기
            if not self.wait_for_comments_load():
                print("댓글이 없는 포스트입니다.")
                return True

            # 5. 현재 페이지 번호 확인
            current_page_num = self.get_current_page_number()

            # 6. 현재 페이지의 댓글 먼저 수집
            print(f"\n--- 현재 페이지 ({current_page_num}) 댓글 수집 ---")
            initial_ids = self.extract_comment_authors()
            print(f"현재 페이지에서 {len(initial_ids)}개 ID 추출")

            # 7. 전체 페이지 수 확인 (더 정확한 방법 사용)
            # 먼저 간단한 방법으로 시도
            total_pages = self.get_total_pages()

            # 만약 현재 페이지가 총 페이지보다 크다면, 실제로 순회해서 확인
            if current_page_num >= total_pages:
                print(
                    f"현재 페이지({current_page_num})가 총 페이지({total_pages})보다 크거나 같음. 실제 확인 필요."
                )
                total_pages = self.go_to_all_pages_and_get_total()

            print(f"\n총 댓글 페이지 수: {total_pages}")

            if total_pages > 1:
                # 1페이지부터 순차적으로 모든 페이지 방문
                for page_num in range(1, total_pages + 1):
                    # 이미 수집한 페이지는 건너뛰기
                    if page_num == current_page_num:
                        continue

                    print(f"\n--- 페이지 {page_num}/{total_pages} 처리 중 ---")

                    if self.go_to_specific_page(page_num):
                        time.sleep(3)  # 페이지 로딩 대기

                        # 댓글이 로드되었는지 확인
                        comment_elements = self.driver.find_elements(
                            By.CSS_SELECTOR, "li.u_cbox_comment"
                        )
                        if comment_elements:
                            current_ids = self.extract_comment_authors()
                            print(f"페이지 {page_num}: {len(current_ids)}개 ID 추출")
                        else:
                            print(f"페이지 {page_num}: 댓글 로드 실패")
                    else:
                        print(f"페이지 {page_num} 이동 실패")

            print(f"\n{'='*60}")
            print(f"추출 완료!")
            print(f"총 페이지 수: {total_pages}")
            print(f"총 댓글 작성자 수: {len(self.extracted_ids)}")
            print(f"{'='*60}")

            return True

        except Exception as e:
            print(f"✗ 댓글 추출 실패: {e}")
            import traceback

            traceback.print_exc()
            return False

    def save_to_file(self, filename="commenter.txt"):
        """추출된 ID를 파일로 저장"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(script_dir, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                for author_id in sorted(self.extracted_ids):
                    f.write(f"{author_id}\n")

            print(f"\n✓ ID 목록이 저장되었습니다: {file_path}")
            print(f"총 {len(self.extracted_ids)}개의 고유 ID")

            # 저장된 내용 미리보기
            if self.extracted_ids:
                print(f"\n저장된 내용 미리보기:")
                for i, author_id in enumerate(sorted(self.extracted_ids)[:10]):
                    print(f"  {author_id}")

                if len(self.extracted_ids) > 10:
                    print(f"  ... 외 {len(self.extracted_ids) - 10}개 더")

            return True

        except Exception as e:
            print(f"✗ 파일 저장 실패: {e}")
            return False

    def close(self):
        """브라우저 종료"""
        if self.driver:
            try:
                self.driver.quit()
                print("\n✓ 브라우저 종료 완료")
            except:
                pass


def main():
    """메인 실행 함수"""
    print("네이버 블로그 댓글 작성자 ID 추출기")
    print("=" * 50)

    # URL 입력받기
    post_url = input("네이버 블로그 포스트 URL을 입력하세요: ").strip()

    if not post_url:
        print("✗ URL이 입력되지 않았습니다.")
        return

    if "blog.naver.com" not in post_url:
        print("✗ 네이버 블로그 URL이 아닙니다.")
        return

    # 헤드리스 모드 선택
    headless_input = (
        input("헤드리스 모드로 실행하시겠습니까? (y/n, 기본값: n): ").strip().lower()
    )
    headless = headless_input in ["y", "yes"]

    # 댓글 추출기 실행
    extractor = CommentExtractor(headless=headless)

    try:
        if not extractor.driver:
            print("✗ 브라우저 초기화에 실패했습니다.")
            return

        # 댓글 추출 및 저장
        if extractor.extract_all_comments(post_url):
            extractor.save_to_file()

    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")

    except Exception as e:
        print(f"\n✗ 예상치 못한 오류: {e}")

    finally:
        extractor.close()


if __name__ == "__main__":
    main()
