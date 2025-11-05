import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    GUILD_ID = int(os.getenv('GUILD_ID', 0))
    
    # 게임 설정
    POSITIONS = ['탱', '딜', '힐']
    TEAM_SIZE = 5
    MIN_GAMES_FOR_STATS = 3
    
    # 데이터베이스 설정
    DATABASE_PATH = 'database/rallyup.db'
    
    # 점수 시스템
    WIN_SCORE_CHANGE = 25
    LOSE_SCORE_CHANGE = -15

class EventSystemSettings:
    """이벤트 시스템 설정"""
    
    # 이벤트 기간
    EVENT_START_DATE = "11월 5일"
    EVENT_END_DATE = "12월 21일"
    EVENT_DESCRIPTION = f"**기간**: {EVENT_START_DATE} ~ {EVENT_END_DATE}"
    
    # 보너스 점수
    DAILY_ALL_CLEAR_BONUS = 5  # 일일 퀘스트 전체 완료 보너스
    FOUR_PLAYERS_BONUS = 1      # 4명 참여 보너스
    
    # 카테고리 정보
    CATEGORY_INFO = {
        'daily': {
            'name': '📅 일일 퀘스트',
            'emoji': '📅',
            'description': '매일 진행할 수 있는 기본 미션'
        },
        'online': {
            'name': '💻 온라인 특별',
            'emoji': '💻',
            'description': '온라인에서 진행하는 특별 미션'
        },
        'offline': {
            'name': '🏃 오프라인 특별',
            'emoji': '🏃',
            'description': '오프라인 활동 미션'
        },
        'hidden': {
            'name': '🎁 히든 미션',
            'emoji': '🎁',
            'description': '숨겨진 특별 미션'
        }
    }
    
    # 순위 이모지
    RANK_EMOJIS = {
        1: "🥇",
        2: "🥈",
        3: "🥉"
    }
    
    # Embed 색상
    class Colors:
        SUCCESS = 0x00ff88
        INFO = 0x0099ff
        WARNING = 0xffaa00
        ERROR = 0xff6b6b
        GOLD = 0xffd700
        EVENT = 0xff6b9d