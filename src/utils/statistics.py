import json
import os
from datetime import datetime, date
from typing import Dict, Any


class Statistics:
    """활동 통계 관리"""

    def __init__(self, stats_file: str = "stats.json"):
        self.stats_file = stats_file
        self.stats = self.load_stats()

    def load_stats(self) -> Dict:
        """통계 파일 로드"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return self.get_default_stats()
        else:
            return self.get_default_stats()

    def get_default_stats(self) -> Dict:
        """기본 통계 구조"""
        return {
            "total_visits": 0,
            "total_comments": 0,
            "daily_stats": {},
            "weekly_stats": {},
            "monthly_stats": {},
            "average_stay_time": 0,
            "last_activity": None,
        }

    def save_stats(self):
        """통계 저장"""
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"통계 저장 실패: {e}")

    def add_visit(self, stay_time: float = 0):
        """방문 기록 추가"""
        self.stats["total_visits"] += 1

        # 평균 체류시간 업데이트
        if stay_time > 0:
            total_time = self.stats["average_stay_time"] * (
                self.stats["total_visits"] - 1
            )
            self.stats["average_stay_time"] = (total_time + stay_time) / self.stats[
                "total_visits"
            ]

        # 일일 통계
        today = date.today().isoformat()
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {"visits": 0, "comments": 0}
        self.stats["daily_stats"][today]["visits"] += 1

        self.stats["last_activity"] = datetime.now().isoformat()
        self.save_stats()

    def add_comment(self):
        """댓글 기록 추가"""
        self.stats["total_comments"] += 1

        # 일일 통계
        today = date.today().isoformat()
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {"visits": 0, "comments": 0}
        self.stats["daily_stats"][today]["comments"] += 1

        self.stats["last_activity"] = datetime.now().isoformat()
        self.save_stats()

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        today = date.today().isoformat()
        today_stats = self.stats["daily_stats"].get(today, {"visits": 0, "comments": 0})

        return {
            "total_visits": self.stats["total_visits"],
            "total_comments": self.stats["total_comments"],
            "today": today_stats,
            "average_stay_time": round(self.stats["average_stay_time"], 1),
            "last_activity": self.stats["last_activity"],
        }

    def get_daily_stats(self, days: int = 7) -> Dict[str, Dict]:
        """최근 N일 통계"""
        from datetime import timedelta

        result = {}
        for i in range(days):
            day = (date.today() - timedelta(days=i)).isoformat()
            if day in self.stats["daily_stats"]:
                result[day] = self.stats["daily_stats"][day]
            else:
                result[day] = {"visits": 0, "comments": 0}

        return result
