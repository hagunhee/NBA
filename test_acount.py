import os
import json
from src.core.config import Config
from src.core.security import SecurityManager

# 테스트 계정 정보
TEST_ID = "your_naver_id"
TEST_PW = "your_password"

# 1. 설정 저장 테스트
print("1. 계정 정보 저장 테스트")
config = Config()
sm = SecurityManager()

# 암호화
encrypted_pw = sm.encrypt_password(TEST_PW)

# 저장
config.set("account", "naver_id", TEST_ID)
config.set("account", "naver_pw", encrypted_pw)
config.set("account", "save_id", True)
config.set("account", "save_pw", True)
config.save()

print(f"저장 완료: ID={TEST_ID}")

# 2. 설정 불러오기 테스트
print("\n2. 계정 정보 불러오기 테스트")
config2 = Config()

loaded_id = config2.get("account", "naver_id", "")
loaded_pw = config2.get("account", "naver_pw", "")

print(f"불러온 ID: {loaded_id}")
print(f"ID 일치: {loaded_id == TEST_ID}")

if loaded_pw:
    decrypted_pw = sm.decrypt_password(loaded_pw)
    print(f"비밀번호 복호화 성공: {decrypted_pw == TEST_PW}")

# 3. 파일 내용 확인
print("\n3. config.json 파일 내용")
with open("config.json", "r", encoding="utf-8") as f:
    print(json.dumps(json.load(f), indent=2, ensure_ascii=False))
