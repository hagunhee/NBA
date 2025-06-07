import json
import os
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv


class Config:
    """프로그램 설정 관리"""

    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """설정 파일 로드"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    # 기본 설정과 병합
                    default = self.get_default_config()
                    self._merge_config(default, config_data)
                    return default
            except Exception as e:
                print(f"설정 파일 로드 실패: {e}")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def _merge_config(self, default: Dict, loaded: Dict):
        """로드된 설정을 기본 설정에 병합"""
        for key, value in loaded.items():
            if (
                isinstance(value, dict)
                and key in default
                and isinstance(default[key], dict)
            ):
                self._merge_config(default[key], value)
            else:
                default[key] = value

    def get_default_config(self) -> Dict:
        """기본 설정"""
        return {
            "license": {"key": ""},
            "profiles": {},  # 프로필 시스템 추가
            "current_profile": "",  # 현재 선택된 프로필
            "account": {  # 하위 호환성을 위해 유지
                "naver_id": "",
                "naver_pw": "",
                "save_id": False,
                "save_pw": False,
            },
            "automation": {
                "min_stay_time": 60,
                "max_stay_time": 180,
                "delay_min": 10,
                "delay_max": 30,
                "daily_limit": 20,
                "scroll_speed": "보통",
                "natural_scroll": True,
                "auto_comment": True,
                "auto_like": True,
                "comment_style": "친근함",
                "retry_count": 3,
                "continue_on_error": True,
                "auto_restart": False,
            },
            "browser": {
                "headless": False,
                "window_size": "1280x800",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            "cache": {"enabled": True, "ttl_days": 7, "max_entries": 1000},
            "update": {"auto_check": True, "check_interval": 86400, "last_check": ""},
            "logging": {"level": "기본"},
        }

    def save(self):
        """설정 저장"""
        try:
            # 디렉토리가 없으면 생성
            os.makedirs(
                os.path.dirname(os.path.abspath(self.config_file)), exist_ok=True
            )

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            print(f"설정 저장 완료: {self.config_file}")

        except Exception as e:
            print(f"설정 저장 실패: {e}")

    # === 프로필 관련 메서드 추가 ===

    def get_profiles(self) -> Dict[str, Dict]:
        """모든 프로필 가져오기"""
        return self.config.get("profiles", {})

    def get_profile(self, profile_name: str) -> Optional[Dict]:
        """특정 프로필 가져오기"""
        return self.config.get("profiles", {}).get(profile_name)

    def save_profile(
        self, profile_name: str, naver_id: str, naver_pw: str, save_pw: bool = True
    ):
        """프로필 저장"""
        if "profiles" not in self.config:
            self.config["profiles"] = {}

        self.config["profiles"][profile_name] = {
            "naver_id": naver_id,
            "naver_pw": naver_pw if save_pw else "",
            "save_pw": save_pw,
            "created_at": (
                os.path.getmtime(self.config_file)
                if os.path.exists(self.config_file)
                else None
            ),
        }

        # 현재 프로필로 설정
        self.config["current_profile"] = profile_name

        # 하위 호환성을 위해 account 섹션도 업데이트
        self.config["account"] = {
            "naver_id": naver_id,
            "naver_pw": naver_pw if save_pw else "",
            "save_id": True,
            "save_pw": save_pw,
        }

        self.save()

    def delete_profile(self, profile_name: str):
        """프로필 삭제"""
        if "profiles" in self.config and profile_name in self.config["profiles"]:
            del self.config["profiles"][profile_name]

            # 현재 프로필이 삭제된 경우 초기화
            if self.config.get("current_profile") == profile_name:
                self.config["current_profile"] = ""
                self.config["account"] = {
                    "naver_id": "",
                    "naver_pw": "",
                    "save_id": False,
                    "save_pw": False,
                }

            self.save()

    def set_current_profile(self, profile_name: str):
        """현재 프로필 설정"""
        if profile_name in self.config.get("profiles", {}):
            self.config["current_profile"] = profile_name

            # account 섹션도 업데이트
            profile = self.config["profiles"][profile_name]
            self.config["account"] = {
                "naver_id": profile.get("naver_id", ""),
                "naver_pw": profile.get("naver_pw", ""),
                "save_id": True,
                "save_pw": profile.get("save_pw", False),
            }

            self.save()
            return True
        return False

    def get_current_profile_name(self) -> str:
        """현재 프로필 이름 가져오기"""
        return self.config.get("current_profile", "")

    def get_profile_names(self) -> List[str]:
        """모든 프로필 이름 목록"""
        return list(self.config.get("profiles", {}).keys())

    # === 기존 메서드들 ===

    def get(self, section: str, key: str, default: Any = None) -> Any:
        """설정값 가져오기"""
        try:
            value = self.config[section][key]
            return value
        except KeyError:
            return default

    def set(self, section: str, key: str, value: Any):
        """설정값 저장"""
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value

    def remove(self, section: str, key: str):
        """설정값 삭제"""
        try:
            if section in self.config and key in self.config[section]:
                del self.config[section][key]
        except KeyError:
            pass

    def get_section(self, section: str) -> Optional[Dict]:
        """섹션 전체 가져오기"""
        return self.config.get(section, {})

    def has_key(self, section: str, key: str) -> bool:
        """키 존재 여부 확인"""
        try:
            return section in self.config and key in self.config[section]
        except:
            return False

    def clear_section(self, section: str):
        """섹션 전체 삭제"""
        if section in self.config:
            self.config[section] = {}

    def reset_to_default(self):
        """기본 설정으로 초기화"""
        self.config = self.get_default_config()
        self.save()
