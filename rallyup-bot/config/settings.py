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