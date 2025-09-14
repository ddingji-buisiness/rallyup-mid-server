from datetime import datetime, timedelta, timezone
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')
UTC = pytz.timezone('UTC')

class TimeUtils:
    @staticmethod
    def get_kst_now():
        """현재 한국 시간 반환 (timezone-aware)"""
        return datetime.now(KST)
    
    @staticmethod
    def get_utc_now():
        """현재 UTC 시간 반환 (timezone-aware)"""
        return datetime.now(UTC)
    
    @staticmethod
    def kst_to_utc(kst_time):
        """KST 시간을 UTC로 변환"""
        if kst_time.tzinfo is None:
            kst_time = KST.localize(kst_time)
        return kst_time.astimezone(UTC)
    
    @staticmethod
    def utc_to_kst(utc_time):
        """UTC 시간을 KST로 변환"""
        if utc_time.tzinfo is None:
            utc_time = UTC.localize(utc_time)
        return utc_time.astimezone(KST)
    
    @staticmethod
    def parse_db_timestamp(timestamp_str):
        """DB에서 가져온 timestamp를 UTC timezone-aware datetime으로 변환"""
        # CURRENT_TIMESTAMP는 UTC로 저장되므로 UTC로 파싱
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = UTC.localize(dt)
        return dt
    
    @staticmethod
    def get_discord_timestamp(dt):
        """Discord timestamp 형식으로 변환"""
        if dt.tzinfo is None:
            # naive datetime이면 KST로 가정
            dt = KST.localize(dt)
        return int(dt.timestamp())