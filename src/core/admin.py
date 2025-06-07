"""
관리자 도구
"""

import secrets
from .license_manager import LicenseManager


class AdminMenu:
    """관리자 메뉴"""

    def __init__(self):
        self.license_manager = LicenseManager()

    def run(self):
        """관리자 메뉴 실행"""
        while True:
            print("\n" + "=" * 50)
            print("네이버 블로그 자동화 - 관리자 도구")
            print("=" * 50)
            print("1. 라이선스 생성")
            print("2. 라이선스 목록 조회")
            print("0. 종료")
            print("-" * 50)

            choice = input("선택: ").strip()

            if choice == "1":
                self.create_license()
            elif choice == "2":
                self.list_licenses()
            elif choice == "0":
                break
            else:
                print("잘못된 선택입니다.")

    def create_license(self):
        """라이선스 생성"""
        print("\n=== 라이선스 생성 ===")

        license_key = input("라이선스 키 (비워두면 자동 생성): ").strip()
        if not license_key:
            license_key = secrets.token_urlsafe(16)
            print(f"자동 생성된 키: {license_key}")

        customer_email = input("고객 이메일: ").strip()
        if not customer_email:
            print("고객 이메일은 필수입니다.")
            return

        try:
            days = int(input("유효 기간 (일, 0=무제한): ") or "30")
        except ValueError:
            days = 30

        # Firebase에 라이선스 생성
        if self.license_manager.db:
            success = self.license_manager.generate_license(customer_email, days)
            if success:
                print(f"\n✓ 라이선스 생성 완료")
                print(f"  - 라이선스 키: {license_key}")
                print(f"  - 고객: {customer_email}")
                print(
                    f"  - 유효 기간: {days}일" if days > 0 else "  - 유효 기간: 무제한"
                )
            else:
                print("라이선스 생성 실패")
        else:
            print("Firebase 연결이 필요합니다.")

    def list_licenses(self):
        """라이선스 목록 조회"""
        print("\n=== 라이선스 목록 ===")

        if not self.license_manager.db:
            print("Firebase 연결이 필요합니다.")
            return

        try:
            licenses = self.license_manager.db.collection("licenses").get()

            for doc in licenses:
                data = doc.to_dict()
                print(f"\n키: {doc.id}")
                print(f"  고객: {data.get('customer_email', 'Unknown')}")
                print(f"  상태: {'활성' if data.get('active') else '비활성'}")
                print(
                    f"  하드웨어: {'등록됨' if data.get('hardware_id') else '미등록'}"
                )
                print(f"  생성일: {data.get('created_at', 'Unknown')}")

        except Exception as e:
            print(f"목록 조회 실패: {e}")
