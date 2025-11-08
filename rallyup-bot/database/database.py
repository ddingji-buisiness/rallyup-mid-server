import logging
import aiosqlite
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from utils.time_utils import TimeUtils

import discord
from database.models import BestPairSummary, ClanScrim, ClanTeam, ScrimRecruitment, TeamWinrateAnalysis, TeammatePairStats, User, Match, Participant, UserMatchup, WordleAttempt, WordleGame, WordleGuess, WordleRating
import uuid
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "database/rallyup.db"):
        self.db_path = db_path

    def get_connection(self):
        """데이터베이스 연결 반환 (연속형 챌린지용)"""
        return aiosqlite.connect(self.db_path)

    def generate_uuid(self) -> str:
        """UUID 생성"""
        return str(uuid.uuid4())
    
    async def initialize(self):
        """데이터베이스 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA synchronous=NORMAL') 
            await db.execute('PRAGMA cache_size=10000')
            await db.execute('PRAGMA temp_store=memory')
            await db.execute('PRAGMA busy_timeout=30000')

            await self.initialize_clan_tables()
            await self.initialize_server_settings_tables()
            await self.create_bamboo_tables()
            await self.initialize_wordle_tables()
            await self.create_inter_guild_scrim_tables()
            await self.initialize_voice_level_tables()
            await self.create_scrim_settings_table()
            await self.create_auto_schedule_tables()
            await self.create_inquiry_tables()
            await self.create_consultation_tables()
            await self.initialize_event_system_tables()

            # users 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    discord_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    total_games INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    tank_games INTEGER DEFAULT 0,
                    tank_wins INTEGER DEFAULT 0,
                    dps_games INTEGER DEFAULT 0,
                    dps_wins INTEGER DEFAULT 0,
                    support_games INTEGER DEFAULT 0,
                    support_wins INTEGER DEFAULT 0,
                    score INTEGER DEFAULT 1000,
                    total_sessions INTEGER DEFAULT 0,
                    wordle_points INTEGER DEFAULT 10000,
                    daily_points_claimed TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # user_applications 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    birth_year TEXT NOT NULL,
                    entry_method TEXT NOT NULL,
                    battle_tag TEXT NOT NULL,
                    main_position TEXT NOT NULL,
                    previous_season_tier TEXT NOT NULL,
                    current_season_tier TEXT NOT NULL,
                    highest_tier TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by TEXT,
                    admin_note TEXT,
                    UNIQUE(guild_id, user_id)
                )
            ''')
            
            # registered_users 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS registered_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    birth_year TEXT NOT NULL,
                    entry_method TEXT NOT NULL,
                    battle_tag TEXT NOT NULL,
                    main_position TEXT NOT NULL,
                    previous_season_tier TEXT NOT NULL,
                    current_season_tier TEXT NOT NULL,
                    highest_tier TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    wordle_points INTEGER DEFAULT 10000,
                    daily_points_claimed TEXT,
                    UNIQUE(guild_id, user_id)
                )
            ''')

            # nickname_format_settings 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS nickname_format_settings (
                    guild_id TEXT PRIMARY KEY,
                    format_template TEXT,
                    required_fields TEXT
                )
            ''')

            # user_battle_tags 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_battle_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    battle_tag TEXT NOT NULL,
                    account_type TEXT DEFAULT 'sub',
                    is_primary BOOLEAN DEFAULT FALSE,
                    rank_info TEXT,
                    platform TEXT DEFAULT 'pc',
                    region TEXT DEFAULT 'asia',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id, battle_tag)
                )
            ''')

            # 서버 관리자 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    added_by TEXT NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(guild_id, user_id)
                )
            ''')
            
            # matches 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    match_uuid TEXT NOT NULL UNIQUE,
                    team1_channel TEXT NOT NULL,
                    team2_channel TEXT NOT NULL,
                    winning_team INTEGER NOT NULL,
                    has_position_data BOOLEAN DEFAULT FALSE,
                    session_id INTEGER,
                    match_number INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES scrim_sessions (id)
                )
            ''')
            
            # participants 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    team_num INTEGER NOT NULL,
                    position_order INTEGER NOT NULL,
                    position TEXT,
                    won BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches (id)
                )
            ''')
            
            # user_matchups 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_matchups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user1_id TEXT NOT NULL,
                    user2_id TEXT NOT NULL,
                    user1_position TEXT,
                    user2_position TEXT,
                    user1_wins INTEGER DEFAULT 0,
                    user2_wins INTEGER DEFAULT 0,
                    total_matches INTEGER DEFAULT 0,
                    last_match_date TIMESTAMP,
                    UNIQUE(user1_id, user2_id, user1_position, user2_position)
                )
            ''')

            # teammate_combinations 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS teammate_combinations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    user1_id TEXT NOT NULL,
                    user2_id TEXT NOT NULL,
                    user1_position TEXT,
                    user2_position TEXT,
                    won BOOLEAN NOT NULL,
                    team_num INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES matches (id),
                    UNIQUE(match_id, user1_id, user2_id)
                )
            ''')

            # scrim_sessions 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    session_uuid TEXT NOT NULL UNIQUE,
                    voice_channel TEXT NOT NULL,
                    session_name TEXT,
                    total_participants INTEGER NOT NULL,
                    session_status TEXT DEFAULT 'active',
                    started_by TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    total_matches INTEGER DEFAULT 0
                )
            ''')

            # session_participants 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS session_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    join_order INTEGER NOT NULL,
                    is_present BOOLEAN DEFAULT TRUE,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES scrim_sessions (id),
                    UNIQUE(session_id, user_id)
                )
            ''')

            # scrim_recruitments 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_recruitments (
                    id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    scrim_date TEXT NOT NULL,
                    deadline TEXT NOT NULL,
                    channel_id TEXT,
                    message_id TEXT,
                    status TEXT DEFAULT 'active',
                    created_by TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recruitment_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('joined', 'declined', 'late_join')),
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (recruitment_id) REFERENCES scrim_recruitments(id),
                    UNIQUE(recruitment_id, user_id)
                )
            ''')

            # match_results 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS match_results (
                    id TEXT PRIMARY KEY,
                    recruitment_id TEXT NOT NULL,
                    match_number INTEGER NOT NULL,
                    team_a_score INTEGER DEFAULT 0,
                    team_b_score INTEGER DEFAULT 0,
                    winning_team TEXT NOT NULL CHECK (winning_team IN ('team_a', 'team_b')),
                    match_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    FOREIGN KEY (recruitment_id) REFERENCES scrim_recruitments(id)
                )
            ''')
            
            # 경기 참가자 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS match_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    team TEXT NOT NULL CHECK (team IN ('team_a', 'team_b')),
                    position TEXT NOT NULL CHECK (position IN ('탱커', '딜러', '힐러')),
                    won BOOLEAN NOT NULL,
                    FOREIGN KEY (match_id) REFERENCES match_results(id)
                )
            ''')
            
            # 사용자 통계 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    total_games INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    tank_games INTEGER DEFAULT 0,
                    tank_wins INTEGER DEFAULT 0,
                    dps_games INTEGER DEFAULT 0,
                    dps_wins INTEGER DEFAULT 0,
                    support_games INTEGER DEFAULT 0,
                    support_wins INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, guild_id)
                )
            ''')

            # 배틀태그 로그 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS battle_tag_log_settings (
                    guild_id TEXT PRIMARY KEY,
                    log_channel_id TEXT,
                    log_add BOOLEAN DEFAULT TRUE,
                    log_delete BOOLEAN DEFAULT TRUE,
                    log_primary_change BOOLEAN DEFAULT TRUE,
                    log_tier_change BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # voice_monitor_settings 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_monitor_settings (
                    guild_id TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # TTS 로그 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tts_log_settings (
                    guild_id TEXT PRIMARY KEY,
                    log_channel_id TEXT,
                    enabled BOOLEAN DEFAULT TRUE,
                    auto_create_thread BOOLEAN DEFAULT TRUE,
                    thread_auto_archive_duration INTEGER DEFAULT 1440,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # TTS 일일 스레드 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tts_daily_threads (
                    guild_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    thread_id TEXT NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, date)
                )
            ''')

            # 개인별 TTS 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_tts_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    default_voice TEXT DEFAULT '인준',
                    default_rate TEXT DEFAULT '+0%',
                    default_pitch TEXT DEFAULT '+0Hz',
                    default_volume TEXT DEFAULT '+0%',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                );
            ''')
            
            # TTS 전용 채널 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS tts_channel_settings (
                    guild_id TEXT PRIMARY KEY,
                    dedicated_channel_id TEXT,
                    auto_filter_short_reactions BOOLEAN DEFAULT TRUE,
                    min_message_length INTEGER DEFAULT 2,
                    filter_emoji_only BOOLEAN DEFAULT TRUE, 
                    filter_bot_messages BOOLEAN DEFAULT TRUE, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_participants_match_id ON participants(match_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_participants_user_id ON participants(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_matchups_users ON user_matchups(user1_id, user2_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_matches_uuid ON matches(match_uuid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_matches_session ON matches(session_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_teammate_combinations_users ON teammate_combinations(user1_id, user2_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_teammate_combinations_match ON teammate_combinations(match_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_scrim_sessions_guild ON scrim_sessions(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_scrim_sessions_status ON scrim_sessions(session_status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_participants_session ON session_participants(session_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_participants_user ON session_participants(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_users_sessions ON users(total_sessions)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_applications_guild ON user_applications(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_applications_status ON user_applications(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_registered_users_guild ON registered_users(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_guild ON server_admins(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_user ON server_admins(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_battle_tags_user ON user_battle_tags(guild_id, user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_battle_tags_tag ON user_battle_tags(battle_tag)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_voice_monitor_guild ON voice_monitor_settings(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_tts_log_guild ON tts_log_settings(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_tts_daily_threads_guild_date ON tts_daily_threads(guild_id, date)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_tts_prefs ON user_tts_preferences(guild_id, user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_tts_channel_guild ON tts_channel_settings(guild_id)')

            await db.commit()

    async def initialize_event_system_tables(self):
        """이벤트 시스템 테이블 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 1. 팀 정보 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_teams (
                    team_id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(guild_id, team_name)
                )
            ''')
            
            # 2. 팀원 구성 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_team_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id) ON DELETE CASCADE,
                    UNIQUE(team_id, user_id)
                )
            ''')
            
            # 3. 미션 정보 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_missions (
                    mission_id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    mission_name TEXT NOT NULL,
                    description TEXT,
                    base_points INTEGER NOT NULL,
                    category TEXT NOT NULL CHECK (category IN ('daily', 'offline', 'online', 'hidden')),
                    min_participants INTEGER DEFAULT 1,
                    bonus_conditions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            ''')
            
            # 4. 미션 완료 기록 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_mission_completions (
                    completion_id TEXT PRIMARY KEY,
                    team_id TEXT NOT NULL,
                    mission_id TEXT NOT NULL,
                    participants_count INTEGER NOT NULL,
                    awarded_points INTEGER NOT NULL,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_by TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id),
                    FOREIGN KEY (mission_id) REFERENCES event_missions(mission_id)
                )
            ''')

            # 5. 음성 채널 활동 세션 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_voice_sessions (
                    session_id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    team_id TEXT NOT NULL,
                    member_count INTEGER NOT NULL,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    hours_completed INTEGER DEFAULT 0,
                    points_awarded INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    session_end TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id)
                )
            ''')

            # 7. 음성 채널 팀 일일 점수 테이블 (오전 9시 기준)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_team_daily_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_score INTEGER DEFAULT 0,
                    sessions TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id) ON DELETE CASCADE,
                    UNIQUE(team_id, date)
                )
            ''')

            # 6. 음성 채널 활동 점수 로그 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_voice_activity_log (
                    log_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    team_id TEXT NOT NULL,
                    points_awarded INTEGER NOT NULL,
                    member_count INTEGER NOT NULL,
                    hours_at_award INTEGER NOT NULL,
                    awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT,
                    FOREIGN KEY (session_id) REFERENCES event_voice_sessions(session_id),
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id)
                )
            ''')

            # 7. 음성 채널 팀 일일 점수 테이블 (오전 9시 기준)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_team_daily_scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_score INTEGER DEFAULT 0,
                    sessions TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id) ON DELETE CASCADE,
                    UNIQUE(team_id, date)
                )
            ''')

            # 8. 공지 채널 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS event_announcement_channels (
                    guild_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 9. 활성 음성 세션 테이블 (봇 재시작 시 복구용)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_voice_sessions (
                    team_id TEXT PRIMARY KEY,
                    team_name TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    members TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    last_check_time TEXT NOT NULL,
                    hours_awarded INTEGER DEFAULT 0,
                    is_bonus_mode BOOLEAN DEFAULT FALSE,
                    bonus_start_time TEXT,
                    member_count INTEGER NOT NULL,
                    channel_history TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (team_id) REFERENCES event_teams(team_id) ON DELETE CASCADE
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_teams_guild ON event_teams(guild_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_team_members_team ON event_team_members(team_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_team_members_user ON event_team_members(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_missions_guild ON event_missions(guild_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_completions_team ON event_mission_completions(team_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_completions_mission ON event_mission_completions(mission_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_voice_sessions_team ON event_voice_sessions(team_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_voice_sessions_guild ON event_voice_sessions(guild_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_voice_activity_log_session ON event_voice_activity_log(session_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_event_voice_activity_log_team ON event_voice_activity_log(team_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_voice_team_daily_scores_team_date ON voice_team_daily_scores(team_id, date)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_active_voice_sessions_team ON active_voice_sessions(team_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_active_voice_sessions_guild ON active_voice_sessions(guild_id)')

            await db.commit()
            print("✅ 이벤트 시스템 테이블 생성 완료")

    async def create_auto_schedule_tables(self):
        """정기 내전 자동 스케줄 테이블 생성"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_auto_schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    schedule_name TEXT NOT NULL,
                    recurrence_type TEXT NOT NULL DEFAULT 'weekly',
                    recurrence_interval INTEGER NOT NULL DEFAULT 1,
                    day_of_week INTEGER NOT NULL,
                    scrim_time TEXT NOT NULL,
                    post_days_before INTEGER NOT NULL DEFAULT 0,
                    recruitment_title TEXT NOT NULL,
                    recruitment_description TEXT,
                    deadline_type TEXT NOT NULL DEFAULT 'relative',
                    deadline_value TEXT NOT NULL,
                    reminder_enabled BOOLEAN DEFAULT FALSE,
                    reminder_hours_before INTEGER DEFAULT 5,
                    channel_id TEXT NOT NULL,
                    send_dm_notification BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    last_created_date TEXT,
                    next_scheduled_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT NOT NULL,
                    
                    UNIQUE(guild_id, schedule_name)
                )
            ''')
            
            # 인덱스 생성
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_auto_schedules_guild 
                ON scrim_auto_schedules(guild_id)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_auto_schedules_active 
                ON scrim_auto_schedules(is_active, day_of_week)
            ''')
            
            await db.commit()
            print("✅ Auto schedule tables initialized")

    async def create_consultation_tables(self):
        """1:1 상담 관련 테이블 생성"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 1:1 상담 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS consultations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_number TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    admin_id TEXT NOT NULL,
                    admin_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    is_urgent BOOLEAN DEFAULT FALSE,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'completed')),
                    request_message_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    accepted_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    completed_by TEXT
                )
            ''')
            
            # 인덱스 생성
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_consultations_guild_user 
                ON consultations(guild_id, user_id)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_consultations_status 
                ON consultations(status, created_at)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_consultations_admin 
                ON consultations(guild_id, admin_id, status)
            ''')

            await db.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_active_consultation_per_user
                ON consultations(guild_id, user_id)
                WHERE status IN ('pending', 'accepted')
            ''')
            
            await db.commit()
            print("✅ 1:1 상담 테이블이 생성되었습니다.")

    async def create_inquiry_tables(self):
        """문의 시스템 관련 테이블 생성"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 문의/티켓 메인 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inquiries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_number TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    inquiry_type TEXT NOT NULL CHECK (inquiry_type IN ('team', 'private')),
                    category TEXT NOT NULL,
                    title TEXT,
                    content TEXT NOT NULL,
                    is_anonymous BOOLEAN DEFAULT FALSE,
                    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'closed')),
                    assigned_to TEXT,
                    channel_message_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    resolved_by TEXT
                )
            ''')
            
            # 문의 로그 테이블 (누가 언제 무엇을 했는지 기록)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inquiry_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inquiry_id INTEGER NOT NULL,
                    admin_id TEXT NOT NULL,
                    admin_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
                )
            ''')
            
            # 익명 작성자 확인 로그 (프라이버시 보호)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inquiry_reveal_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inquiry_id INTEGER NOT NULL,
                    admin_id TEXT NOT NULL,
                    admin_name TEXT NOT NULL,
                    revealed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (inquiry_id) REFERENCES inquiries(id)
                )
            ''')
            
            # 서버별 문의 시스템 설정
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inquiry_settings (
                    guild_id TEXT PRIMARY KEY,
                    team_inquiry_channel_id TEXT,
                    allowed_categories TEXT,
                    daily_limit INTEGER DEFAULT 3,
                    enable_anonymous BOOLEAN DEFAULT TRUE,
                    enable_private_inquiry BOOLEAN DEFAULT TRUE,
                    notification_role_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 쿨다운 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inquiry_cooldowns (
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    cooldown_until TIMESTAMP NOT NULL,
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id)
                )
            ''')
            
            # 인덱스 생성 (성능 최적화)
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_inquiries_guild_user 
                ON inquiries(guild_id, user_id)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_inquiries_status 
                ON inquiries(status, created_at)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_inquiries_ticket 
                ON inquiries(guild_id, ticket_number)
            ''')
            
            await db.commit()
            print("✅ 문의 시스템 테이블이 생성되었습니다.")

    async def initialize_voice_level_tables(self):
        """음성 레벨 시스템 테이블 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 음성 세션 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_uuid TEXT NOT NULL UNIQUE,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    join_time TIMESTAMP NOT NULL,
                    leave_time TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_muted BOOLEAN DEFAULT FALSE,
                    is_screen_sharing BOOLEAN DEFAULT FALSE,
                    duration_seconds INTEGER DEFAULT 0,
                    muted_seconds INTEGER DEFAULT 0,
                    screen_share_seconds INTEGER DEFAULT 0,
                    is_solo BOOLEAN DEFAULT FALSE,
                    last_solo_marked_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 유저 간 관계 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user1_id TEXT NOT NULL,
                    user2_id TEXT NOT NULL,
                    total_time_seconds INTEGER DEFAULT 0,
                    last_played_together TIMESTAMP,
                    relationship_multiplier REAL DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user1_id, user2_id),
                    CHECK(user1_id < user2_id)
                )
            ''')
            
            # 유저 레벨 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    current_level INTEGER DEFAULT 0,
                    current_exp INTEGER DEFAULT 0,
                    total_exp INTEGER DEFAULT 0,
                    total_play_time_seconds INTEGER DEFAULT 0,
                    total_screen_share_seconds INTEGER DEFAULT 0,
                    unique_partners_count INTEGER DEFAULT 0,
                    last_exp_gain TIMESTAMP,
                    daily_exp_gained INTEGER DEFAULT 0,
                    last_daily_reset TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, user_id)
                )
            ''')

            # 음성 세션 파트너 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS session_partners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_uuid TEXT NOT NULL,
                    partner_id TEXT NOT NULL,
                    joined_together_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (session_uuid) REFERENCES voice_sessions(session_uuid),
                    UNIQUE(session_uuid, partner_id)
                )
            ''')
            
            # 서버별 설정 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS voice_level_settings (
                    guild_id TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT FALSE,
                    notification_channel_id TEXT,
                    base_exp_per_minute REAL DEFAULT 10.0,
                    daily_exp_limit INTEGER DEFAULT 5000,
                    min_session_minutes INTEGER DEFAULT 30,
                    check_mute_status BOOLEAN DEFAULT TRUE,
                    screen_share_bonus_enabled BOOLEAN DEFAULT TRUE,
                    screen_share_multiplier REAL DEFAULT 1.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_voice_sessions_active ON voice_sessions(guild_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_voice_sessions_user ON voice_sessions(user_id, is_active)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_relationships_guild ON user_relationships(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_relationships_users ON user_relationships(user1_id, user2_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_levels_guild ON user_levels(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_levels_user ON user_levels(guild_id, user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_partners_session ON session_partners(session_uuid)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_session_partners_partner ON session_partners(partner_id)')

            await db.commit()
            print("✅ Voice level system tables initialized")

    async def initialize_clan_tables(self):
        """클랜전 관련 테이블 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 클랜 팀 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clan_teams (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    clan_name TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, clan_name)
                )
            ''')
            
            # 클랜전 스크림 세션 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clan_scrims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    scrim_uuid TEXT NOT NULL UNIQUE,
                    clan_a_name TEXT NOT NULL,
                    clan_b_name TEXT NOT NULL,
                    voice_channel_a TEXT NOT NULL,
                    voice_channel_b TEXT NOT NULL,
                    scrim_status TEXT DEFAULT 'active',
                    started_by TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP,
                    total_matches INTEGER DEFAULT 0,
                    clan_a_wins INTEGER DEFAULT 0,
                    clan_b_wins INTEGER DEFAULT 0,
                    FOREIGN KEY (clan_a_name) REFERENCES clan_teams (clan_name),
                    FOREIGN KEY (clan_b_name) REFERENCES clan_teams (clan_name)
                )
            ''')
            
            # 클랜전 개별 경기 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clan_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrim_id INTEGER NOT NULL,
                    match_uuid TEXT NOT NULL UNIQUE,
                    match_number INTEGER NOT NULL,
                    map_name TEXT NOT NULL,
                    map_type TEXT,
                    winning_team TEXT NOT NULL,
                    score_a INTEGER,
                    score_b INTEGER,
                    has_position_data BOOLEAN DEFAULT FALSE,
                    has_composition_data BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scrim_id) REFERENCES clan_scrims (id)
                )
            ''')
            
            # 클랜전 참가자 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clan_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    clan_name TEXT NOT NULL,
                    team_side TEXT NOT NULL,
                    position TEXT,
                    position_order INTEGER DEFAULT 0,
                    won BOOLEAN NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES clan_matches (id)
                )
            ''')
            
            # 클랜전 팀 조합 테이블 (Optional)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS clan_compositions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER NOT NULL,
                    team_side TEXT NOT NULL,
                    hero_1 TEXT,
                    hero_2 TEXT,
                    hero_3 TEXT,
                    hero_4 TEXT,
                    hero_5 TEXT,
                    composition_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES clan_matches (id),
                    UNIQUE(match_id, team_side)
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_teams_guild ON clan_teams(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_scrims_guild ON clan_scrims(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_scrims_status ON clan_scrims(scrim_status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_matches_scrim ON clan_matches(scrim_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_participants_match ON clan_participants(match_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_clan_participants_user ON clan_participants(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_guild ON server_admins(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_user ON server_admins(user_id)')
            
            await db.commit()

    async def create_scrim_settings_table(self):
        """내전 설정 테이블 생성 (채널 설정, 자동 스케줄링 등)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_settings (
                    guild_id TEXT PRIMARY KEY,
                    recruitment_channel_id TEXT,
                    auto_schedule_enabled BOOLEAN DEFAULT FALSE,
                    schedule_day INTEGER,
                    schedule_time TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_scrim_settings_guild 
                ON scrim_settings(guild_id)
            ''')
            
            await db.commit()
            print("✅ Scrim settings table initialized")

    async def initialize_server_settings_tables(self):
        """서버 설정 테이블 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 서버 설정 테이블 생성
            await db.execute('''
                CREATE TABLE IF NOT EXISTS server_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL UNIQUE,
                    newbie_role_id TEXT,
                    member_role_id TEXT,
                    auto_role_change BOOLEAN DEFAULT FALSE,
                    welcome_channel_id TEXT,
                    recruitment_channel_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_settings_guild ON server_settings(guild_id)')
            
            await db.commit()
            print("✅ Server settings tables initialized")

    async def create_bamboo_tables(self):
        """대나무숲 관련 테이블 생성"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 대나무숲 메시지 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bamboo_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    message_id TEXT NOT NULL UNIQUE,
                    author_id TEXT NOT NULL,
                    original_content TEXT NOT NULL,
                    message_type TEXT NOT NULL CHECK (message_type IN ('anonymous', 'timed_reveal')),
                    reveal_time INTEGER,
                    is_revealed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    revealed_at TIMESTAMP
                )
            ''')
            
            # 성능 최적화를 위한 인덱스 생성
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_bamboo_reveal_time 
                ON bamboo_messages(reveal_time, is_revealed) 
                WHERE message_type = 'timed_reveal'
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_bamboo_guild_created
                ON bamboo_messages(guild_id, created_at)
            ''')
            
            await db.commit()
            print("🎋 대나무숲 테이블이 생성되었습니다.")

    async def _update_teammate_combinations_in_transaction(self, db, match_id: int):
        """팀메이트 조합 데이터 업데이트 (트랜잭션 내에서 실행)"""
        # 각 팀별로 팀메이트 조합 생성
        for team_num in [1, 2]:
            # 해당 팀의 참가자들 조회
            async with db.execute('''
                SELECT user_id, position, won
                FROM participants 
                WHERE match_id = ? AND team_num = ?
                ORDER BY position_order
            ''', (match_id, team_num)) as cursor:
                team_members = await cursor.fetchall()
                
                # 팀 내 모든 2명 조합 생성
                for i in range(len(team_members)):
                    for j in range(i + 1, len(team_members)):
                        user1_id, user1_pos, won = team_members[i]
                        user2_id, user2_pos, _ = team_members[j]
                        
                        # 사용자 ID 순서 정렬 (일관성을 위해)
                        if user1_id > user2_id:
                            user1_id, user2_id = user2_id, user1_id
                            user1_pos, user2_pos = user2_pos, user1_pos
                        
                        # 팀메이트 조합 기록
                        await db.execute('''
                            INSERT OR IGNORE INTO teammate_combinations 
                            (match_id, user1_id, user2_id, user1_position, user2_position, won, team_num)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (match_id, user1_id, user2_id, user1_pos, user2_pos, won, team_num))
    
    async def get_or_create_user_in_transaction(self, db, discord_id: str, username: str):
        """트랜잭션 내에서 유저 생성 또는 업데이트 (연결 재사용)"""
        await db.execute('''
            INSERT INTO users (discord_id, username) 
            VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username = excluded.username,
                updated_at = CURRENT_TIMESTAMP
        ''', (discord_id, username))
    
    async def get_or_create_user(self, discord_id: str, username: str) -> User:
        """유저 정보 가져오기 또는 생성 (별도 연결용)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA busy_timeout=30000')
            
            await self.get_or_create_user_in_transaction(db, discord_id, username)
            await db.commit()
            
            # 사용자 정보 조회
            async with db.execute(
                'SELECT * FROM users WHERE discord_id = ?', 
                (discord_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    return User(
                        discord_id=row[0],
                        username=row[1],
                        total_games=row[2],
                        total_wins=row[3],
                        tank_games=row[4],
                        tank_wins=row[5],
                        dps_games=row[6],
                        dps_wins=row[7],
                        support_games=row[8],
                        support_wins=row[9],
                        score=row[10],
                        created_at=datetime.fromisoformat(row[11]) if row[11] else None,
                        updated_at=datetime.fromisoformat(row[12]) if row[12] else None
                    )
                else:
                    return User(
                        discord_id=discord_id,
                        username=username,
                        created_at=datetime.now()
                    )
    
    async def create_match(self, guild_id: str, team1_channel: str, team2_channel: str, 
                      winning_team: int, team1_members: List, team2_members: List) -> str:
        """새 매치 생성 및 참가자 등록 (세션 연동)"""
        match_uuid = str(uuid.uuid4())
        
        for attempt in range(3):
            try:
                async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                    await db.execute('PRAGMA journal_mode=WAL')
                    await db.execute('PRAGMA busy_timeout=30000')
                    
                    # 활성 세션 확인
                    session_id = None
                    match_number = 1
                    
                    async with db.execute('''
                        SELECT id, total_matches FROM scrim_sessions 
                        WHERE guild_id = ? AND session_status = 'active'
                        ORDER BY started_at DESC LIMIT 1
                    ''', (guild_id,)) as cursor:
                        session_row = await cursor.fetchone()
                        if session_row:
                            session_id = session_row[0]
                            match_number = session_row[1] + 1
                    
                    # 매치 생성 (세션 정보 포함)
                    cursor = await db.execute('''
                        INSERT INTO matches 
                        (guild_id, match_uuid, team1_channel, team2_channel, winning_team, session_id, match_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (guild_id, match_uuid, team1_channel, team2_channel, winning_team, session_id, match_number))
                    
                    match_id = cursor.lastrowid
                    
                    print(f"🔍 [DB] 매치 ID 생성: {match_id}, 세션 ID: {session_id}, 경기 번호: {match_number}")
                    
                    # 세션의 경기 수 업데이트
                    if session_id:
                        await db.execute('''
                            UPDATE scrim_sessions SET total_matches = ? WHERE id = ?
                        ''', (match_number, session_id))
                    
                    # 모든 사용자를 한 번에 생성
                    all_members = team1_members + team2_members
                    for member in all_members:
                        await self.get_or_create_user_in_transaction(db, str(member.id), member.display_name)
                    print(f"🔍 [DB] 사용자 {len(all_members)}명 생성 완료")
                    
                    # 팀1 참가자 등록
                    for i, member in enumerate(team1_members):
                        await db.execute('''
                            INSERT INTO participants 
                            (match_id, user_id, username, team_num, position_order, won)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (match_id, str(member.id), member.display_name, 1, i+1, winning_team == 1))
                    
                    # 팀2 참가자 등록
                    for i, member in enumerate(team2_members):
                        await db.execute('''
                            INSERT INTO participants 
                            (match_id, user_id, username, team_num, position_order, won)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (match_id, str(member.id), member.display_name, 2, i+1, winning_team == 2))
                    
                    print(f"🔍 [DB] 참가자 {len(all_members)}명 등록 완료")
                    
                    # 기본 통계 업데이트
                    await self._update_basic_stats_in_transaction(db, match_id)
                    print("🔍 [DB] 기본 통계 업데이트 완료")
                    
                    # 승점 계산
                    await self._update_scores_in_transaction(db, match_id, winning_team)
                    print("🔍 [DB] 승점 업데이트 완료")
                    
                    # 모든 작업을 한 번에 커밋
                    await db.commit()
                    print(f"🔍 [DB] 트랜잭션 커밋 완료: {match_uuid}")
                    
                    return match_uuid
                    
            except Exception as e:
                print(f"❌ [DB] 시도 {attempt+1} 실패: {str(e)}")
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    raise e
    
    async def _update_basic_stats_in_transaction(self, db, match_id: int):
        """기본 통계 업데이트 (트랜잭션 내에서 실행)"""
        # 각 참가자의 기본 통계 업데이트
        async with db.execute(
            'SELECT user_id, won FROM participants WHERE match_id = ?',
            (match_id,)
        ) as cursor:
            participants = await cursor.fetchall()
            
            for user_id, won in participants:
                await db.execute('''
                    UPDATE users 
                    SET total_games = total_games + 1,
                        total_wins = total_wins + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (1 if won else 0, user_id))

    async def create_scrim_session(self, guild_id: str, voice_channel: str, participants: List, 
                              started_by: str, session_name: str = None) -> str:
        """새 내전 세션 생성"""
        session_uuid = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            await db.execute('PRAGMA busy_timeout=30000')
            
            # 세션 생성
            cursor = await db.execute('''
                INSERT INTO scrim_sessions 
                (guild_id, session_uuid, voice_channel, session_name, total_participants, started_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (guild_id, session_uuid, voice_channel, session_name, len(participants), started_by))
            
            session_id = cursor.lastrowid
            
            # 참여자 등록
            for i, participant in enumerate(participants):
                await db.execute('''
                    INSERT INTO session_participants 
                    (session_id, user_id, username, join_order)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, str(participant.id), participant.display_name, i + 1))
                
                # 사용자 테이블에서 세션 참여 업데이트
                await self.get_or_create_user_in_transaction(db, str(participant.id), participant.display_name)
            
            await db.commit()
            return session_uuid

    async def get_active_session(self, guild_id: str) -> Optional[dict]:
        """활성 세션 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM scrim_sessions 
                WHERE guild_id = ? AND session_status = 'active'
                ORDER BY started_at DESC
                LIMIT 1
            ''', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def get_active_session_details(self, guild_id: str) -> Optional[tuple]:
        """활성 세션의 상세 정보 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            # 세션 정보
            async with db.execute('''
                SELECT * FROM scrim_sessions 
                WHERE guild_id = ? AND session_status = 'active'
                ORDER BY started_at DESC
                LIMIT 1
            ''', (guild_id,)) as cursor:
                session_row = await cursor.fetchone()
                if not session_row:
                    return None
                
                columns = [description[0] for description in cursor.description]
                session = dict(zip(columns, session_row))
            
            # 참여자 정보
            async with db.execute('''
                SELECT * FROM session_participants 
                WHERE session_id = ?
                ORDER BY join_order
            ''', (session['id'],)) as cursor:
                participant_rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                participants = [dict(zip(columns, row)) for row in participant_rows]
            
            # 해당 세션의 경기들
            async with db.execute('''
                SELECT * FROM matches 
                WHERE session_id = ?
                ORDER BY created_at
            ''', (session['id'],)) as cursor:
                match_rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                matches = [dict(zip(columns, row)) for row in match_rows]
            
            return session, participants, matches
    
    async def end_scrim_session(self, session_id: int):
        """세션 종료"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 세션 상태 업데이트
            await db.execute('''
                UPDATE scrim_sessions 
                SET session_status = 'completed', ended_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (session_id,))
            
            # 해당 세션 경기 수 업데이트
            async with db.execute('''
                SELECT COUNT(*) FROM matches WHERE session_id = ?
            ''', (session_id,)) as cursor:
                match_count = (await cursor.fetchone())[0]
            
            await db.execute('''
                UPDATE scrim_sessions SET total_matches = ? WHERE id = ?
            ''', (match_count, session_id))
            
            await db.commit()

    async def update_participation_counts(self, participants: List):
        """참여자들의 세션 참여 횟수 업데이트"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            for participant in participants:
                await db.execute('''
                    UPDATE users 
                    SET total_sessions = total_sessions + 1,
                        last_session_date = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (str(participant.id),))
            
            await db.commit()


    async def _update_scores_in_transaction(self, db, match_id: int, winning_team: int):
        """승점 업데이트 (트랜잭션 내에서 실행)"""
        # 승리팀 +25점, 패배팀 -15점
        WIN_SCORE = 25
        LOSE_SCORE = -15
        
        async with db.execute(
            'SELECT user_id, team_num FROM participants WHERE match_id = ?',
            (match_id,)
        ) as cursor:
            participants = await cursor.fetchall()
            
            for user_id, team_num in participants:
                if team_num == winning_team:
                    # 승리팀
                    await db.execute('''
                        UPDATE users 
                        SET score = score + ?
                        WHERE discord_id = ?
                    ''', (WIN_SCORE, user_id))
                else:
                    # 패배팀 (최소 100점 보장)
                    await db.execute('''
                        UPDATE users 
                        SET score = MAX(100, score + ?)
                        WHERE discord_id = ?
                    ''', (LOSE_SCORE, user_id))
    
    async def add_position_data(self, match_uuid: str, team1_positions: str, team2_positions: str):
        """매치에 포지션 정보 추가"""
        for attempt in range(3):
            try:
                async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                    await db.execute('PRAGMA journal_mode=WAL')
                    await db.execute('PRAGMA busy_timeout=30000')
                    
                    # 매치 ID 찾기
                    async with db.execute(
                        'SELECT id FROM matches WHERE match_uuid = ?', 
                        (match_uuid,)
                    ) as cursor:
                        row = await cursor.fetchone()
                        if not row:
                            raise ValueError(f"매치를 찾을 수 없습니다: {match_uuid}")
                        
                        match_id = row[0]
                    
                    # 팀1 포지션 업데이트
                    team1_pos_list = list(team1_positions)
                    for i, position in enumerate(team1_pos_list):
                        await db.execute('''
                            UPDATE participants 
                            SET position = ?
                            WHERE match_id = ? AND team_num = 1 AND position_order = ?
                        ''', (position, match_id, i+1))
                    
                    # 팀2 포지션 업데이트
                    team2_pos_list = list(team2_positions)
                    for i, position in enumerate(team2_pos_list):
                        await db.execute('''
                            UPDATE participants 
                            SET position = ?
                            WHERE match_id = ? AND team_num = 2 AND position_order = ?
                        ''', (position, match_id, i+1))
                    
                    await db.execute('''
                        UPDATE matches SET has_position_data = TRUE WHERE id = ?
                    ''', (match_id,))
                    
                    await self._update_position_stats_in_transaction(db, match_id)
                    await self._update_matchups_in_transaction(db, match_id)
                    await self._update_teammate_combinations_in_transaction(db, match_id)

                    await db.commit()
                    return
                    
            except Exception as e:
                print(f"❌ [DB] 포지션 추가 시도 {attempt+1} 실패: {str(e)}")
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                else:
                    raise e
                
    async def get_best_teammates(self, user_id: str, min_matches: int = 3):
        """베스트 팀메이트 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    CASE 
                        WHEN tc.user1_id = ? THEN u2.username
                        ELSE u1.username
                    END as teammate_name,
                    CASE 
                        WHEN tc.user1_id = ? THEN tc.user2_id
                        ELSE tc.user1_id
                    END as teammate_id,
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN tc.won THEN 1 ELSE 0 END) as wins,
                    ROUND((SUM(CASE WHEN tc.won THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as winrate
                FROM teammate_combinations tc
                JOIN users u1 ON tc.user1_id = u1.discord_id
                JOIN users u2 ON tc.user2_id = u2.discord_id
                WHERE (tc.user1_id = ? OR tc.user2_id = ?)
                GROUP BY teammate_name, teammate_id
                HAVING COUNT(*) >= ?
                ORDER BY winrate DESC, total_matches DESC
                LIMIT 10
            ''', (user_id, user_id, user_id, user_id, min_matches)) as cursor:
                return await cursor.fetchall()

    async def get_position_synergy(self, user_id: str, min_matches: int = 3):
        """포지션 조합별 궁합 분석"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    CASE 
                        WHEN tc.user1_id = ? THEN tc.user1_position
                        ELSE tc.user2_position
                    END as my_position,
                    CASE 
                        WHEN tc.user1_id = ? THEN tc.user2_position
                        ELSE tc.user1_position
                    END as teammate_position,
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN tc.won THEN 1 ELSE 0 END) as wins,
                    ROUND((SUM(CASE WHEN tc.won THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as winrate
                FROM teammate_combinations tc
                WHERE (tc.user1_id = ? OR tc.user2_id = ?)
                AND tc.user1_position IS NOT NULL 
                AND tc.user2_position IS NOT NULL
                GROUP BY my_position, teammate_position
                HAVING COUNT(*) >= ?
                ORDER BY winrate DESC
            ''', (user_id, user_id, user_id, user_id, min_matches)) as cursor:
                return await cursor.fetchall()
    
    async def _update_position_stats_in_transaction(self, db, match_id: int):
        """포지션별 통계 업데이트"""
        async with db.execute('''
            SELECT user_id, position, won 
            FROM participants 
            WHERE match_id = ? AND position IS NOT NULL
        ''', (match_id,)) as cursor:
            participants = await cursor.fetchall()
            
            for user_id, position, won in participants:
                if position == '탱':
                    await db.execute('''
                        UPDATE users 
                        SET tank_games = tank_games + 1,
                            tank_wins = tank_wins + ?
                        WHERE discord_id = ?
                    ''', (1 if won else 0, user_id))
                elif position == '딜':
                    await db.execute('''
                        UPDATE users 
                        SET dps_games = dps_games + 1,
                            dps_wins = dps_wins + ?
                        WHERE discord_id = ?
                    ''', (1 if won else 0, user_id))
                elif position == '힐':
                    await db.execute('''
                        UPDATE users 
                        SET support_games = support_games + 1,
                            support_wins = support_wins + ?
                        WHERE discord_id = ?
                    ''', (1 if won else 0, user_id))
    
    async def _update_matchups_in_transaction(self, db, match_id: int):
        """개인 매치업 업데이트 (트랜잭션 내에서 실행)"""
        # 양팀 참가자 가져오기
        async with db.execute('''
            SELECT user_id, position, won, team_num
            FROM participants 
            WHERE match_id = ? AND position IS NOT NULL
            ORDER BY team_num, position_order
        ''', (match_id,)) as cursor:
            participants = await cursor.fetchall()
            
            team1 = [p for p in participants if p[3] == 1]
            team2 = [p for p in participants if p[3] == 2]
            
            # 모든 조합의 매치업 업데이트
            for t1_user in team1:
                for t2_user in team2:
                    user1_id, user1_pos, user1_won = t1_user[0], t1_user[1], t1_user[2]
                    user2_id, user2_pos, user2_won = t2_user[0], t2_user[1], t2_user[2]
                    
                    # 사용자 ID 순서 정렬 (일관성을 위해)
                    if user1_id > user2_id:
                        user1_id, user2_id = user2_id, user1_id
                        user1_pos, user2_pos = user2_pos, user1_pos
                        user1_won, user2_won = user2_won, user1_won
                    
                    # 매치업 업데이트 또는 생성
                    await db.execute('''
                        INSERT INTO user_matchups 
                        (user1_id, user2_id, user1_position, user2_position, 
                         user1_wins, user2_wins, total_matches, last_match_date)
                        VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                        ON CONFLICT(user1_id, user2_id, user1_position, user2_position) 
                        DO UPDATE SET
                            user1_wins = user1_wins + ?,
                            user2_wins = user2_wins + ?,
                            total_matches = total_matches + 1,
                            last_match_date = CURRENT_TIMESTAMP
                    ''', (
                        user1_id, user2_id, user1_pos, user2_pos,
                        1 if user1_won else 0, 1 if user2_won else 0,
                        1 if user1_won else 0, 1 if user2_won else 0
                    ))

    async def find_recent_match(self, guild_id: str, user_id: str, minutes: int = 10) -> Optional[str]:
        """최근 매치 찾기 (포지션 추가용)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA busy_timeout=30000')
            
            async with db.execute('''
                SELECT m.match_uuid 
                FROM matches m
                LEFT JOIN participants p ON m.id = p.match_id
                WHERE m.guild_id = ? 
                AND m.has_position_data = FALSE
                AND datetime(m.created_at) > datetime('now', '-{} minutes')
                AND (
                    p.user_id = ? OR  -- 실제 사용자가 참여한 매치
                    m.team1_channel = '개발-A팀'  -- 개발용 매치
                )
                ORDER BY m.created_at DESC
                LIMIT 1
            '''.format(minutes), (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def find_recent_dev_match(self, guild_id: str, minutes: int = 10) -> Optional[str]:
        """개발용 매치만 찾기 (dev_commands 전용)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA busy_timeout=30000')
            
            async with db.execute('''
                SELECT match_uuid 
                FROM matches 
                WHERE guild_id = ? 
                AND team1_channel = '개발-A팀' 
                AND team2_channel = '개발-B팀'
                AND has_position_data = FALSE
                AND datetime(created_at) > datetime('now', '-{} minutes')
                ORDER BY created_at DESC 
                LIMIT 1
            '''.format(minutes), (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    
    async def get_match_participants(self, match_uuid: str) -> Tuple[List[Participant], List[Participant]]:
        """매치 참가자 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA busy_timeout=30000')
            
            # 매치 ID 찾기
            async with db.execute(
                'SELECT id FROM matches WHERE match_uuid = ?', 
                (match_uuid,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return [], []
                
                match_id = row[0]
            
            # 참가자 조회
            async with db.execute('''
                SELECT * FROM participants 
                WHERE match_id = ? 
                ORDER BY team_num, position_order
            ''', (match_id,)) as cursor:
                rows = await cursor.fetchall()
                
                team1_participants = []
                team2_participants = []
                
                for row in rows:
                    participant = Participant(
                        id=row[0],
                        match_id=row[1],
                        user_id=row[2],
                        username=row[3],
                        team_num=row[4],
                        position_order=row[5],
                        position=row[6],
                        won=bool(row[7]),
                        created_at=datetime.fromisoformat(row[8]) if row[8] else None
                    )
                    
                    if participant.team_num == 1:
                        team1_participants.append(participant)
                    else:
                        team2_participants.append(participant)
                
                return team1_participants, team2_participants

    async def get_user_session_stats(self, user_id: str, days: int = 30):
        """사용자의 세션 참여 통계"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    COUNT(DISTINCT sp.session_id) as sessions_joined,
                    COUNT(DISTINCT DATE(s.started_at)) as active_days,
                    AVG(s.total_matches) as avg_matches_per_session,
                    MAX(s.started_at) as last_session_date
                FROM session_participants sp
                JOIN scrim_sessions s ON sp.session_id = s.id
                WHERE sp.user_id = ? 
                AND s.started_at > datetime('now', '-{} days')
                AND s.session_status = 'completed'
            '''.format(days), (user_id,)) as cursor:
                return await cursor.fetchone()

    async def get_popular_session_times(self, guild_id: str, days: int = 30):
        """인기 세션 시간대 분석"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    strftime('%H', started_at) as hour,
                    COUNT(*) as session_count,
                    AVG(total_participants) as avg_participants,
                    AVG(total_matches) as avg_matches
                FROM scrim_sessions
                WHERE guild_id = ? 
                AND started_at > datetime('now', '-{} days')
                AND session_status = 'completed'
                GROUP BY strftime('%H', started_at)
                ORDER BY session_count DESC
            '''.format(days), (guild_id,)) as cursor:
                return await cursor.fetchall()

    async def get_session_participation_rate(self, guild_id: str, days: int = 30):
        """세션 참여율 분석"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    u.username,
                    COUNT(DISTINCT sp.session_id) as sessions_joined,
                    COUNT(DISTINCT s.id) as total_sessions,
                    ROUND((COUNT(DISTINCT sp.session_id) * 100.0 / COUNT(DISTINCT s.id)), 1) as participation_rate
                FROM users u
                CROSS JOIN scrim_sessions s
                LEFT JOIN session_participants sp ON u.discord_id = sp.user_id AND sp.session_id = s.id
                WHERE s.guild_id = ?
                AND s.started_at > datetime('now', '-{} days')
                AND s.session_status = 'completed'
                AND u.total_games > 0
                GROUP BY u.discord_id, u.username
                HAVING COUNT(DISTINCT s.id) > 0
                ORDER BY participation_rate DESC
                LIMIT 10
            '''.format(days), (guild_id,)) as cursor:
                return await cursor.fetchall()

    async def register_clan(self, guild_id: str, clan_name: str, created_by: str) -> bool:
        """클랜 등록"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                await db.execute('''
                    INSERT INTO clan_teams (guild_id, clan_name, created_by)
                    VALUES (?, ?, ?)
                ''', (guild_id, clan_name, created_by))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                # 이미 등록된 클랜
                return False

    async def get_registered_clans(self, guild_id: str) -> List[ClanTeam]:
        """등록된 클랜 목록 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM clan_teams 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
            ''', (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                
                clans = []
                for row in rows:
                    clans.append(ClanTeam(
                        id=row[0],
                        guild_id=row[1],
                        clan_name=row[2],
                        created_by=row[3],
                        is_active=bool(row[4]),
                        created_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        updated_at=datetime.fromisoformat(row[6]) if row[6] else None
                    ))
                return clans

    # 클랜전 세션 관리 메서드들
    async def create_clan_scrim(self, guild_id: str, clan_a: str, clan_b: str,
                            voice_channel_a: str, voice_channel_b: str, started_by: str) -> str:
        """클랜전 스크림 세션 생성"""
        scrim_uuid = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 스크림 세션 생성
            cursor = await db.execute('''
                INSERT INTO clan_scrims 
                (guild_id, scrim_uuid, clan_a_name, clan_b_name, voice_channel_a, voice_channel_b, started_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, scrim_uuid, clan_a, clan_b, voice_channel_a, voice_channel_b, started_by))
            
            await db.commit()
            return scrim_uuid

    async def get_active_clan_scrim(self, guild_id: str) -> Optional[ClanScrim]:
        """활성 클랜전 스크림 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM clan_scrims 
                WHERE guild_id = ? AND scrim_status = 'active'
                ORDER BY started_at DESC
                LIMIT 1
            ''', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return ClanScrim(
                        id=row[0],
                        guild_id=row[1],
                        scrim_uuid=row[2],
                        clan_a_name=row[3],
                        clan_b_name=row[4],
                        voice_channel_a=row[5],
                        voice_channel_b=row[6],
                        scrim_status=row[7],
                        started_by=row[8],
                        started_at=datetime.fromisoformat(row[9]) if row[9] else None,
                        ended_at=datetime.fromisoformat(row[10]) if row[10] else None,
                        total_matches=row[11],
                        clan_a_wins=row[12],
                        clan_b_wins=row[13]
                    )
                return None

    async def create_clan_match(self, guild_id: str, team_a_channel: str, team_b_channel: str,
                            winning_channel: str, map_name: str, 
                            team_a_members: List, team_b_members: List) -> str:
        """클랜전 개별 경기 생성"""
        match_uuid = str(uuid.uuid4())
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 활성 스크림 조회
            scrim = await self.get_active_clan_scrim(guild_id)
            if not scrim:
                raise ValueError("진행 중인 클랜전 스크림이 없습니다")
            
            # 승리팀 결정
            if winning_channel.lower() == team_a_channel.lower():
                winning_team = "clan_a"
                clan_a_win = True
            else:
                winning_team = "clan_b" 
                clan_a_win = False
            
            # 경기 번호 결정
            match_number = scrim.total_matches + 1
            
            # 경기 생성
            cursor = await db.execute('''
                INSERT INTO clan_matches 
                (scrim_id, match_uuid, match_number, map_name, winning_team)
                VALUES (?, ?, ?, ?, ?)
            ''', (scrim.id, match_uuid, match_number, map_name, winning_team))
            
            match_id = cursor.lastrowid
            
            # 참가자 등록 (A팀)
            for i, member in enumerate(team_a_members):
                await db.execute('''
                    INSERT INTO clan_participants 
                    (match_id, user_id, username, clan_name, team_side, position_order, won)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (match_id, str(member.id), member.display_name, scrim.clan_a_name, 
                    "clan_a", i+1, clan_a_win))
            
            # 참가자 등록 (B팀)
            for i, member in enumerate(team_b_members):
                await db.execute('''
                    INSERT INTO clan_participants 
                    (match_id, user_id, username, clan_name, team_side, position_order, won)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (match_id, str(member.id), member.display_name, scrim.clan_b_name,
                    "clan_b", i+1, not clan_a_win))
            
            # 스크림 통계 업데이트
            if clan_a_win:
                await db.execute('''
                    UPDATE clan_scrims 
                    SET total_matches = total_matches + 1, clan_a_wins = clan_a_wins + 1
                    WHERE id = ?
                ''', (scrim.id,))
            else:
                await db.execute('''
                    UPDATE clan_scrims 
                    SET total_matches = total_matches + 1, clan_b_wins = clan_b_wins + 1
                    WHERE id = ?
                ''', (scrim.id,))
            
            await db.commit()
            return match_uuid

    async def add_clan_position_data(self, match_uuid: str, team_side: str, position_data: dict):
        """클랜전 경기에 포지션 정보 추가"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 매치 ID 찾기
            async with db.execute(
                'SELECT id FROM clan_matches WHERE match_uuid = ?', 
                (match_uuid,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"클랜전 경기를 찾을 수 없습니다: {match_uuid}")
                
                match_id = row[0]
            
            # 해당 팀의 참가자들 조회
            async with db.execute('''
                SELECT id, user_id, username, position_order 
                FROM clan_participants 
                WHERE match_id = ? AND team_side = ?
                ORDER BY position_order
            ''', (match_id, team_side)) as cursor:
                participants = await cursor.fetchall()
            
            if len(participants) != 5:
                raise ValueError(f"참가자가 5명이 아닙니다: {len(participants)}명")
            
            # 포지션 매핑 (입력된 사용자명을 실제 user_id와 매칭)
            position_mapping = {
                0: 'tank',    # 1번째 -> 탱커
                1: 'dps1',    # 2번째 -> 딜러1  
                2: 'dps2',    # 3번째 -> 딜러2
                3: 'support1', # 4번째 -> 힐러1
                4: 'support2'  # 5번째 -> 힐러2
            }
            
            # 입력받은 포지션 데이터를 participant_id와 매칭
            for i, (participant_id, user_id, username, position_order) in enumerate(participants):
                position_key = position_mapping[i]
                
                # 해당 포지션에 배정된 사용자명과 현재 참가자 매칭
                assigned_name = position_data.get(position_key, '').strip()
                
                if assigned_name == username or assigned_name == user_id:
                    # 포지션 정보 업데이트
                    position_name = position_key.replace('1', '').replace('2', '')  # dps1 -> dps
                    if position_name == 'tank':
                        position_name = '탱'
                    elif position_name == 'dps':
                        position_name = '딜' 
                    elif position_name == 'support':
                        position_name = '힐'
                    
                    await db.execute('''
                        UPDATE clan_participants 
                        SET position = ?
                        WHERE id = ?
                    ''', (position_name, participant_id))
            
            # 매치의 포지션 데이터 플래그 업데이트
            await db.execute('''
                UPDATE clan_matches 
                SET has_position_data = TRUE 
                WHERE id = ?
            ''', (match_id,))
            
            await db.commit()

    async def add_clan_composition_data(self, match_uuid: str, team_side: str, hero_composition: List[str]):
        """클랜전 경기에 영웅 조합 정보 추가"""
        if len(hero_composition) != 5:
            raise ValueError(f"영웅은 정확히 5명이어야 합니다: {len(hero_composition)}명")
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 매치 ID 찾기
            async with db.execute(
                'SELECT id FROM clan_matches WHERE match_uuid = ?', 
                (match_uuid,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise ValueError(f"클랜전 경기를 찾을 수 없습니다: {match_uuid}")
                
                match_id = row[0]
            
            # 조합 데이터 저장
            await db.execute('''
                INSERT OR REPLACE INTO clan_compositions 
                (match_id, team_side, hero_1, hero_2, hero_3, hero_4, hero_5)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, team_side, *hero_composition))
            
            # 매치의 조합 데이터 플래그 업데이트
            await db.execute('''
                UPDATE clan_matches 
                SET has_composition_data = TRUE 
                WHERE id = ?
            ''', (match_id,))
            
            await db.commit()

    async def get_clan_match_by_uuid(self, match_uuid: str) -> Optional[dict]:
        """UUID로 클랜전 경기 정보 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT cm.*, cs.clan_a_name, cs.clan_b_name, 
                    cs.voice_channel_a, cs.voice_channel_b
                FROM clan_matches cm
                JOIN clan_scrims cs ON cm.scrim_id = cs.id
                WHERE cm.match_uuid = ?
            ''', (match_uuid,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def end_clan_scrim(self, guild_id: str):
        """클랜전 스크림 종료"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            await db.execute('''
                UPDATE clan_scrims 
                SET scrim_status = 'completed', ended_at = CURRENT_TIMESTAMP
                WHERE guild_id = ? AND scrim_status = 'active'
            ''', (guild_id,))
            
            await db.commit()

    async def find_recent_clan_match(self, guild_id: str, minutes: int = 10) -> Optional[str]:
        """최근 클랜전 경기 찾기 (포지션 추가용)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT cm.match_uuid 
                FROM clan_matches cm
                JOIN clan_scrims cs ON cm.scrim_id = cs.id
                WHERE cs.guild_id = ? 
                AND cm.has_position_data = FALSE
                AND datetime(cm.created_at) > datetime('now', '-{} minutes')
                ORDER BY cm.created_at DESC
                LIMIT 1
            '''.format(minutes), (guild_id,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
            
    async def create_user_application(
        self, 
        guild_id: str, 
        user_id: str, 
        username: str,
        entry_method: str, 
        battle_tag: str, 
        birth_year: str, 
        main_position: str,
        previous_season_tier: str, 
        current_season_tier: str, 
        highest_tier: str
    ) -> bool:
        """사용자 신청 생성"""
        
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                print(f"[DEBUG] 신청 데이터 검증 시작:")
                print(f"  - guild_id: {guild_id}")
                print(f"  - user_id: {user_id}")
                print(f"  - username: {username}")
                print(f"  - entry_method: {entry_method}")
                print(f"  - battle_tag: {battle_tag}")
                print(f"  - birth_year: '{birth_year}' (type: {type(birth_year)}, length: {len(birth_year) if birth_year else 0})")
                print(f"  - main_position: {main_position}")
                
                # birth_year 검증
                if not birth_year or len(birth_year) != 2 or not birth_year.isdigit():
                    print(f"❌ birth_year 검증 실패: '{birth_year}'")
                    return False
                
                print(f"[CHECK] ✅ birth_year 검증 통과")
                
                # 기존 신청이 있는지 확인
                async with db.execute('''
                    SELECT status FROM user_applications 
                    WHERE guild_id = ? AND user_id = ?
                ''', (guild_id, user_id)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    print(f"[INFO] 기존 신청 발견 - 상태: {existing[0]}")
                    
                    # 기존 신청 업데이트 (재신청 허용)
                    await db.execute('''
                        UPDATE user_applications 
                        SET username = ?, 
                            entry_method = ?, 
                            battle_tag = ?, 
                            birth_year = ?,
                            main_position = ?, 
                            previous_season_tier = ?, 
                            current_season_tier = ?,
                            highest_tier = ?, 
                            status = 'pending',
                            applied_at = CURRENT_TIMESTAMP,
                            reviewed_at = NULL,
                            reviewed_by = NULL,
                            admin_note = NULL
                        WHERE guild_id = ? AND user_id = ?
                    ''', (
                        username, entry_method, battle_tag, birth_year, 
                        main_position, previous_season_tier, current_season_tier, 
                        highest_tier, guild_id, user_id
                    ))
                    
                    print(f"✅ 기존 신청 업데이트 완료: {username}")
                    
                else:
                    print(f"[INFO] 신규 신청 생성 중...")
                    
                    # 새 신청 생성
                    await db.execute('''
                        INSERT INTO user_applications 
                        (guild_id, user_id, username, birth_year, entry_method, battle_tag, 
                        main_position, previous_season_tier, current_season_tier, highest_tier,
                        status, applied_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    ''', (
                        guild_id, user_id, username, birth_year, entry_method, battle_tag,
                        main_position, previous_season_tier, current_season_tier, highest_tier
                    ))
                    
                    print(f"✅ 신규 신청 생성 완료: {username}")
                
                await db.commit()
                print(f"[SUCCESS] 데이터베이스 커밋 완료")
                return True
                
        except aiosqlite.IntegrityError as e:
            print(f"❌ [DB INTEGRITY ERROR] 데이터 무결성 오류: {e}")
            import traceback
            print(f"   스택트레이스:\n{traceback.format_exc()}")
            return False
            
        except aiosqlite.OperationalError as e:
            print(f"❌ [DB OPERATIONAL ERROR] SQL 실행 오류: {e}")
            import traceback
            print(f"   스택트레이스:\n{traceback.format_exc()}")
            return False
            
        except Exception as e:
            print(f"❌ [FATAL ERROR] 신청 생성/업데이트 예상치 못한 오류: {e}")
            print(f"   오류 타입: {type(e).__name__}")
            import traceback
            print(f"   스택트레이스:\n{traceback.format_exc()}")
            return False

    async def get_user_application(self, guild_id: str, user_id: str) -> Optional[dict]:
        """특정 유저의 신청 정보 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM user_applications 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def get_registered_user_info(self, guild_id: str, user_id: str) -> Optional[dict]:
        """등록된 유저 정보 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM registered_users 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
            
    async def update_registered_user_info(self, guild_id: str, user_id: str, updates: dict) -> bool:
        """등록된 유저 정보 업데이트 (제공된 필드만)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                # 업데이트할 필드가 없으면 실패
                if not updates:
                    return False
                
                # 동적으로 SET 절 생성
                set_clauses = []
                values = []
                
                allowed_fields = ['current_season_tier', 'main_position', 'battle_tag', 'birth_year']
                
                for field in allowed_fields:
                    if field in updates:
                        set_clauses.append(f"{field} = ?")
                        values.append(updates[field])
                
                if not set_clauses:
                    return False
                
                # WHERE 조건용 값 추가
                values.extend([guild_id, user_id])
                
                query = f'''
                    UPDATE registered_users
                    SET {', '.join(set_clauses)}
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                '''
                
                await db.execute(query, values)
                await db.commit()
                
                return True
                
            except Exception as e:
                print(f"❌ 유저 정보 업데이트 실패: {e}")
                import traceback
                print(traceback.format_exc())
                return False

    async def get_pending_applications(self, guild_id: str) -> List[dict]:
        """대기 중인 신청 목록 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM user_applications 
                WHERE guild_id = ? AND status = 'pending'
                ORDER BY applied_at ASC
            ''', (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def reject_user_application(self, guild_id: str, user_id: str, admin_id: str, admin_note: str = None) -> bool:
        """유저 신청 거절"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            cursor = await db.execute('''
                UPDATE user_applications 
                SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP, 
                    reviewed_by = ?, admin_note = ?
                WHERE guild_id = ? AND user_id = ? AND status = 'pending'
            ''', (admin_id, admin_note, guild_id, user_id))
            
            if cursor.rowcount > 0:
                await db.commit()
                return True
            return False

    async def is_user_registered(self, guild_id: str, user_id: str) -> bool:
        """유저가 이미 등록되어 있는지 확인"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT COUNT(*) FROM registered_users 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id)) as cursor:
                count = (await cursor.fetchone())[0]
                return count > 0

    async def get_application_stats(self, guild_id: str) -> dict:
        """신청 통계 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            stats = {}
            
            # 상태별 신청 수
            async with db.execute('''
                SELECT status, COUNT(*) FROM user_applications 
                WHERE guild_id = ? GROUP BY status
            ''', (guild_id,)) as cursor:
                status_counts = await cursor.fetchall()
                stats['status_counts'] = dict(status_counts)
            
            # 등록된 유저 수
            async with db.execute('''
                SELECT COUNT(*) FROM registered_users 
                WHERE guild_id = ? AND is_active = TRUE
            ''', (guild_id,)) as cursor:
                stats['total_registered'] = (await cursor.fetchone())[0]
            
            return stats
        
    async def is_server_admin(self, guild_id: str, user_id: str) -> bool:
        """사용자가 서버 관리자인지 확인"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT COUNT(*) FROM server_admins 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id)) as cursor:
                count = (await cursor.fetchone())[0]
                return count > 0

    async def add_server_admin(self, guild_id: str, user_id: str, username: str, added_by: str) -> bool:
        """서버 관리자 추가"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                await db.execute('''
                    INSERT INTO server_admins (guild_id, user_id, username, added_by)
                    VALUES (?, ?, ?, ?)
                ''', (guild_id, user_id, username, added_by))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                # 이미 관리자인 경우
                return False

    async def remove_server_admin(self, guild_id: str, user_id: str) -> bool:
        """서버 관리자 제거"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            cursor = await db.execute('''
                UPDATE server_admins 
                SET is_active = FALSE 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id))
            
            if cursor.rowcount > 0:
                await db.commit()
                return True
            return False

    async def get_server_admins(self, guild_id: str) -> List[dict]:
        """서버의 모든 관리자 목록 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT user_id, username, added_by, added_at 
                FROM server_admins 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY added_at ASC
            ''', (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_admin_count(self, guild_id: str) -> int:
        """서버의 관리자 수 조회 (서버 소유자 제외)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT COUNT(*) FROM server_admins 
                WHERE guild_id = ? AND is_active = TRUE
            ''', (guild_id,)) as cursor:
                return (await cursor.fetchone())[0]

    async def delete_user_registration(self, guild_id: str, user_id: str) -> tuple[bool, dict]:
        """등록된 유저 삭제 (재신청 가능하도록)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 먼저 등록된 유저 정보 가져오기
            async with db.execute('''
                SELECT * FROM registered_users 
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id)) as cursor:
                user_data = await cursor.fetchone()
                if not user_data:
                    return False, {}
            
            # 등록된 유저 비활성화
            await db.execute('''
                UPDATE registered_users 
                SET is_active = FALSE 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            
            # 기존 신청 기록도 삭제 (재신청 가능하도록)
            await db.execute('''
                DELETE FROM user_applications 
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            
            await db.commit()
            
            # 삭제된 유저 정보 반환
            columns = ['id', 'guild_id', 'user_id', 'username', 'entry_method', 'battle_tag', 
                    'main_position', 'previous_season_tier', 'current_season_tier', 'highest_tier', 
                    'approved_by', 'registered_at', 'is_active']
            user_info = dict(zip(columns, user_data))
            
            return True, user_info

    async def delete_registered_user(self, guild_id: str, user_id: str, admin_id: str, reason: str = None):
        """등록된 유저 삭제"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 등록된 유저인지 확인하고 정보 가져오기
                async with db.execute('''
                    SELECT username FROM registered_users 
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    user = await cursor.fetchone()
                    if not user:
                        return False
                
                # 유저를 비활성화 (삭제하지 않고 is_active = FALSE로 설정)
                await db.execute('''
                    UPDATE registered_users 
                    SET is_active = FALSE
                    WHERE guild_id = ? AND user_id = ?
                ''', (guild_id, user_id))
                
                # 기존 신청 기록도 삭제 (재신청 가능하도록)
                await db.execute('''
                    DELETE FROM user_applications 
                    WHERE guild_id = ? AND user_id = ?
                ''', (guild_id, user_id))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 유저 삭제 오류: {e}")
            import traceback
            print(f"❌ 스택트레이스: {traceback.format_exc()}")
            return False

    async def get_registered_users_list(self, guild_id: str, limit: int = 50):
        """등록된 유저 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                async with db.execute('''
                    SELECT user_id, username, entry_method, battle_tag, main_position, 
                        current_season_tier, registered_at, approved_by
                    FROM registered_users 
                    WHERE guild_id = ? AND is_active = TRUE
                    ORDER BY registered_at DESC
                    LIMIT ?
                ''', (guild_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'entry_method': row[2], 
                            'battle_tag': row[3],      
                            'main_position': row[4],   
                            'current_season_tier': row[5],
                            'registered_at': row[6],   
                            'approved_by': row[7]      
                        }
                        for row in rows
                    ]
        except Exception as e:
            print(f"❌ 등록 유저 목록 조회 오류: {e}")
            return []

    async def search_registered_user(self, guild_id: str, search_term: str) -> List[dict]:
        """등록된 유저 검색 (닉네임, 배틀태그, 유입경로로) - 유입경로 포함"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT user_id, username, entry_method, battle_tag, main_position, current_season_tier, registered_at 
                FROM registered_users 
                WHERE guild_id = ? AND is_active = TRUE 
                AND (username LIKE ? OR battle_tag LIKE ? OR entry_method LIKE ?)
                ORDER BY registered_at DESC
                LIMIT 10
            ''', (guild_id, f'%{search_term}%', f'%{search_term}%', f'%{search_term}%')) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def reset_user_nickname(self, member: discord.Member) -> str:
        """유저 닉네임을 원래대로 복원 (배틀태그 형식에서)"""
        try:
            # 현재 닉네임이 우리 형식인지 확인
            current_nick = member.display_name
            
            # 배틀태그#숫자 / 포지션 / 티어 형식인지 체크
            if '/' in current_nick and len(current_nick.split('/')) >= 2:
                # 우리가 설정한 형식일 가능성이 높음 - Discord 계정명으로 복원
                await member.edit(nick=None)
                return f"Discord 계정명 '{member.name}'으로 복원되었습니다."
            else:
                # 이미 원래 형식이거나 다른 형식 - 그대로 유지
                return f"닉네임 '{current_nick}'을 그대로 유지합니다."
                
        except discord.Forbidden:
            return "닉네임 복원 권한이 부족합니다."
        except discord.HTTPException as e:
            return f"닉네임 복원 실패: {str(e)}"
        except Exception as e:
            return f"닉네임 복원 중 오류: {str(e)}"

    def _shorten_position(self, position: str) -> str:
        """포지션 축약 (닉네임 길이 절약용)"""
        position_map = {
            "탱커": "탱",
            "딜러": "딜", 
            "힐러": "힐",
            "탱커 & 딜러": "탱딜",
            "탱커 & 힐러": "탱힐",
            "딜러 & 힐러": "딜힐",
            "탱커 & 딜러 & 힐러": "탱딜힐" 
        }
        return position_map.get(position, position)

    async def update_server_settings(self, guild_id: str, newbie_role_id: str = None, 
                                    member_role_id: str = None, auto_role_change: bool = True,
                                    welcome_channel_id: str = None):
        """서버 설정 업데이트"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            await db.execute('''
                INSERT INTO server_settings 
                (guild_id, newbie_role_id, member_role_id, auto_role_change, welcome_channel_id, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id) DO UPDATE SET
                    newbie_role_id = COALESCE(excluded.newbie_role_id, server_settings.newbie_role_id),
                    member_role_id = COALESCE(excluded.member_role_id, server_settings.member_role_id),
                    auto_role_change = excluded.auto_role_change,
                    welcome_channel_id = COALESCE(excluded.welcome_channel_id, server_settings.welcome_channel_id),
                    updated_at = CURRENT_TIMESTAMP
            ''', (guild_id, newbie_role_id, member_role_id, auto_role_change, welcome_channel_id))
            
            await db.commit()

    async def get_server_settings(self, guild_id: str) -> dict:
        """서버 설정 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT * FROM server_settings WHERE guild_id = ?
            ''', (guild_id,)) as cursor:
                result = await cursor.fetchone()
                if result:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, result))
                return {}

    async def _update_user_roles_conditional(self, member, guild_id: str) -> str:
        """서버 설정에 따른 조건부 역할 변경"""
        try:
            settings = await self.get_server_settings(guild_id)
            
            # 자동 역할 변경이 비활성화된 경우
            if not settings.get('auto_role_change', False):
                return "ℹ️ 자동 역할 변경이 비활성화됨"
            
            # 역할 ID가 설정되지 않은 경우
            newbie_role_id = settings.get('newbie_role_id')
            member_role_id = settings.get('member_role_id')
            
            if not newbie_role_id or not member_role_id:
                return "⚠️ 역할이 설정되지 않음 (닉네임만 변경)"
            
            # 실제 역할 변경 수행
            return await self._update_user_roles(member, newbie_role_id, member_role_id)
            
        except Exception as e:
            return f"❌ 역할 변경 중 오류: {str(e)}"

    async def _update_user_roles(self, member, newbie_role_id: str, member_role_id: str) -> str:
        """실제 역할 변경 수행"""
        try:
            guild = member.guild
            newbie_role = guild.get_role(int(newbie_role_id))
            member_role = guild.get_role(int(member_role_id))
            
            if not newbie_role:
                return f"❌ 신입 역할을 찾을 수 없음 (ID: {newbie_role_id})"
            
            if not member_role:
                return f"❌ 구성원 역할을 찾을 수 없음 (ID: {member_role_id})"
            
            changes = []
            
            # 신입 역할 제거
            if newbie_role in member.roles:
                await member.remove_roles(newbie_role, reason="RallyUp 유저 승인")
                changes.append(f"제거: {newbie_role.name}")
            
            # 구성원 역할 추가
            if member_role not in member.roles:
                await member.add_roles(member_role, reason="RallyUp 유저 승인") 
                changes.append(f"추가: {member_role.name}")
            
            if changes:
                return f"✅ 역할 변경: {' | '.join(changes)}"
            else:
                return "ℹ️ 이미 올바른 역할 보유"
                
        except discord.Forbidden:
            return "❌ 봇 권한 부족 (역할 관리 권한 필요)"
        except ValueError:
            return "❌ 잘못된 역할 ID 형식"
        except Exception as e:
            return f"❌ 역할 변경 실패: {str(e)}"

    async def _reverse_user_roles_conditional(self, member, guild_id: str) -> str:
        """유저 삭제 시 역할 복구 (구성원 → 신입)"""
        try:
            settings = await self.get_server_settings(guild_id)
            
            # 자동 역할 변경이 비활성화된 경우
            if not settings.get('auto_role_change', False):
                return "ℹ️ 자동 역할 변경이 비활성화됨 (역할 변경 안함)"
            
            # 역할 ID가 설정되지 않은 경우
            newbie_role_id = settings.get('newbie_role_id')
            member_role_id = settings.get('member_role_id')
            
            if not newbie_role_id or not member_role_id:
                return "⚠️ 역할이 설정되지 않음 (역할 변경 안함)"
            
            # 실제 역할 복구 수행 (구성원 → 신입)
            return await self._reverse_user_roles(member, newbie_role_id, member_role_id)
            
        except Exception as e:
            return f"❌ 역할 복구 중 오류: {str(e)}"

    async def _reverse_user_roles(self, member, newbie_role_id: str, member_role_id: str) -> str:
        """실제 역할 복구 수행 (구성원 → 신입)"""
        try:
            guild = member.guild
            newbie_role = guild.get_role(int(newbie_role_id))
            member_role = guild.get_role(int(member_role_id))
            
            if not newbie_role:
                return f"❌ 신입 역할을 찾을 수 없음 (ID: {newbie_role_id})"
            
            if not member_role:
                return f"❌ 구성원 역할을 찾을 수 없음 (ID: {member_role_id})"
            
            changes = []
            
            # 구성원 역할 제거
            if member_role in member.roles:
                await member.remove_roles(member_role, reason="RallyUp 유저 삭제 - 역할 복구")
                changes.append(f"제거: {member_role.name}")
            
            # 신입 역할 추가
            if newbie_role not in member.roles:
                await member.add_roles(newbie_role, reason="RallyUp 유저 삭제 - 역할 복구") 
                changes.append(f"추가: {newbie_role.name}")
            
            if changes:
                return f"✅ 역할 복구: {' | '.join(changes)}"
            else:
                return "ℹ️ 이미 올바른 역할 보유"
                
        except discord.Forbidden:
            return "❌ 봇 권한 부족 (역할 관리 권한 필요)"
        except ValueError:
            return "❌ 잘못된 역할 ID 형식"
        except Exception as e:
            return f"❌ 역할 복구 실패: {str(e)}"

    async def _restore_user_nickname(self, member) -> str:
        """유저 닉네임을 Discord 원래 이름으로 복구"""
        try:
            current_nick = member.display_name
            original_name = member.name  # Discord 원래 사용자명
            
            # 이미 원래 이름이거나 닉네임이 설정되지 않은 경우
            if member.nick is None or current_nick == original_name:
                return f"ℹ️ 닉네임이 이미 원래 상태 ('{original_name}')"
            
            # 현재 닉네임이 RallyUp 봇이 설정한 형식인지 확인
            # 형식: "배틀태그/포지션/티어" 또는 "배틀태그 / 포지션 / 티어"
            if ('/' in current_nick and 
                any(tier in current_nick for tier in ['언랭', '브론즈', '실버', '골드', '플래티넘', '다이아', '마스터', '그마', '챔피언']) and
                any(pos in current_nick for pos in ['탱', '딜', '힐'])):
                
                # RallyUp 형식으로 보이므로 원래 이름으로 복구
                await member.edit(nick=None, reason="RallyUp 유저 삭제 - 닉네임 원상복구")
                return f"✅ 닉네임 복구: '{current_nick}' → '{original_name}'"
            else:
                # RallyUp 형식이 아니므로 그대로 유지
                return f"ℹ️ 커스텀 닉네임으로 보여 그대로 유지: '{current_nick}'"
                
        except discord.Forbidden:
            return "❌ 닉네임 복구 권한이 부족합니다"
        except discord.HTTPException as e:
            return f"❌ 닉네임 복구 실패: {str(e)}"
        except Exception as e:
            return f"❌ 닉네임 복구 중 오류: {str(e)}"

    async def save_bamboo_message(self, guild_id: str, channel_id: str, message_id: str,
                                author_id: str, original_content: str, message_type: str,
                                reveal_time: Optional[int] = None) -> bool:
        """대나무숲 메시지 데이터베이스에 저장"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                utc_now = TimeUtils.get_utc_now().isoformat()

                await db.execute('''
                    INSERT INTO bamboo_messages 
                    (guild_id, channel_id, message_id, author_id, original_content, 
                    message_type, reveal_time, is_revealed, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, FALSE, ?)
                ''', (guild_id, channel_id, message_id, author_id, original_content, 
                    message_type, reveal_time, utc_now))
                
                await db.commit()
                print(f"🎋 메시지 저장 완료 - UTC: {utc_now}, KST: {TimeUtils.get_kst_now()}")
                return True
                
        except Exception as e:
            print(f"대나무숲 메시지 저장 오류: {e}")
            return False

    async def get_bamboo_message(self, message_id: str) -> Optional[Dict]:
        """메시지 ID로 대나무숲 메시지 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM bamboo_messages WHERE message_id = ?
                ''', (message_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
                    
        except Exception as e:
            print(f"대나무숲 메시지 조회 오류: {e}")
            return None

    async def get_pending_reveals(self) -> List[Dict]:
        """공개 시간이 도래한 메시지들 조회"""
        try:
            current_time = int(TimeUtils.get_utc_now().timestamp())
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM bamboo_messages 
                    WHERE message_type = 'timed_reveal' 
                    AND is_revealed = FALSE 
                    AND reveal_time <= ?
                    ORDER BY reveal_time ASC
                ''', (current_time,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    result = [dict(zip(columns, row)) for row in rows]
                    
                    # print(f"🐛 공개 대상 메시지: {len(result)}개")
                    # for msg in result:
                    #     print(f"  - {msg['message_id']}: 예정시간 {msg['reveal_time']}")
                    
                    return result
                    
        except Exception as e:
            print(f"공개 대기 메시지 조회 오류: {e}")
            return []

    async def mark_message_revealed(self, message_id: str) -> bool:
        """메시지를 공개됨으로 표시"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')

                revealed_at_utc = TimeUtils.get_utc_now().isoformat()

                cursor = await db.execute('''
                    UPDATE bamboo_messages 
                    SET is_revealed = TRUE, revealed_at = ?
                    WHERE message_id = ?
                ''', (revealed_at_utc, message_id))
                
                if cursor.rowcount > 0:
                    await db.commit()
                    return True
                return False
                
        except Exception as e:
            print(f"메시지 공개 표시 오류: {e}")
            return False

    async def get_bamboo_statistics(self, guild_id: str) -> Dict:
        """대나무숲 사용 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                stats = {}
                
                # 기본 통계
                async with db.execute('''
                    SELECT 
                        COUNT(*) as total_messages,
                        COUNT(CASE WHEN message_type = 'anonymous' THEN 1 END) as anonymous_messages,
                        COUNT(CASE WHEN message_type = 'timed_reveal' THEN 1 END) as timed_messages,
                        COUNT(CASE WHEN is_revealed = TRUE THEN 1 END) as revealed_messages
                    FROM bamboo_messages 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        stats.update(dict(zip([desc[0] for desc in cursor.description], row)))
                
                # 🔥 수정: 시간별 통계 - KST 기준으로 날짜 계산 후 UTC로 변환
                now_kst = TimeUtils.get_kst_now()
                today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
                week_start_kst = today_start_kst - timedelta(days=7)
                month_start_kst = today_start_kst - timedelta(days=30)
                
                # KST를 UTC로 변환해서 DB 쿼리
                today_start_utc = TimeUtils.kst_to_utc(today_start_kst)
                week_start_utc = TimeUtils.kst_to_utc(week_start_kst)
                month_start_utc = TimeUtils.kst_to_utc(month_start_kst)
                
                print(f"🐛 시간 디버깅 - KST 오늘 시작: {today_start_kst}")
                print(f"🐛 시간 디버깅 - UTC 오늘 시작: {today_start_utc}")
                
                # 오늘 메시지 (KST 기준 오늘)
                async with db.execute('''
                    SELECT COUNT(*) FROM bamboo_messages 
                    WHERE guild_id = ? AND created_at >= ?
                ''', (guild_id, today_start_utc.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    stats['today_messages'] = row[0] if row else 0
                
                # 이번 주 메시지
                async with db.execute('''
                    SELECT COUNT(*) FROM bamboo_messages 
                    WHERE guild_id = ? AND created_at >= ?
                ''', (guild_id, week_start_utc.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    stats['week_messages'] = row[0] if row else 0
                
                # 이번 달 메시지
                async with db.execute('''
                    SELECT COUNT(*) FROM bamboo_messages 
                    WHERE guild_id = ? AND created_at >= ?
                ''', (guild_id, month_start_utc.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    stats['month_messages'] = row[0] if row else 0
                
                # 🔥 수정: 공개 대기 중인 메시지 수 - UTC 기준
                current_timestamp = int(TimeUtils.get_utc_now().timestamp())
                async with db.execute('''
                    SELECT COUNT(*) FROM bamboo_messages 
                    WHERE guild_id = ? AND message_type = 'timed_reveal' 
                    AND is_revealed = FALSE AND reveal_time > ?
                ''', (guild_id, current_timestamp)) as cursor:
                    row = await cursor.fetchone()
                    stats['pending_reveals'] = row[0] if row else 0
                
                # 다음 공개 예정 시간
                async with db.execute('''
                    SELECT MIN(reveal_time) FROM bamboo_messages 
                    WHERE guild_id = ? AND message_type = 'timed_reveal' 
                    AND is_revealed = FALSE AND reveal_time > ?
                ''', (guild_id, current_timestamp)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        stats['next_reveal'] = f"<t:{row[0]}:R>"
                    else:
                        stats['next_reveal'] = "없음"
                
                return stats
                
        except Exception as e:
            print(f"대나무숲 통계 조회 오류: {e}")
            # 기본값 반환
            return {
                'total_messages': 0,
                'anonymous_messages': 0, 
                'timed_messages': 0,
                'revealed_messages': 0,
                'today_messages': 0,
                'week_messages': 0,
                'month_messages': 0,
                'pending_reveals': 0,
                'next_reveal': '없음'
            }

    async def get_user_bamboo_messages(self, guild_id: str, author_id: str, limit: int = 10) -> List[Dict]:
        """특정 사용자의 대나무숲 메시지 조회 (관리자용)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT message_id, original_content, message_type, is_revealed, 
                        created_at, reveal_time, revealed_at
                    FROM bamboo_messages 
                    WHERE guild_id = ? AND author_id = ?
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (guild_id, author_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"사용자 대나무숲 메시지 조회 오류: {e}")
            return []

    async def cleanup_old_bamboo_messages(self, days_old: int = 365) -> int:
        """오래된 대나무숲 메시지 정리"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 오래된 메시지 삭제 (공개된 메시지 또는 완전 익명 메시지)
                cursor = await db.execute('''
                    DELETE FROM bamboo_messages 
                    WHERE created_at < ? 
                    AND (is_revealed = TRUE OR message_type = 'anonymous')
                ''', (cutoff_date.isoformat(),))
                
                deleted_count = cursor.rowcount
                await db.commit()
                
                if deleted_count > 0:
                    print(f"🎋 {deleted_count}개의 오래된 대나무숲 메시지가 정리되었습니다.")
                
                return deleted_count
                
        except Exception as e:
            print(f"대나무숲 메시지 정리 오류: {e}")
            return 0

    async def get_bamboo_message_by_author(self, guild_id: str, author_id: str, 
                                        message_content: str) -> Optional[Dict]:
        """작성자와 내용으로 메시지 찾기 (중복 방지용)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # 최근 1시간 내 동일한 작성자의 동일한 내용 메시지 확인
                one_hour_ago = datetime.now() - timedelta(hours=1)
                
                async with db.execute('''
                    SELECT * FROM bamboo_messages 
                    WHERE guild_id = ? AND author_id = ? 
                    AND original_content = ? AND created_at >= ?
                    ORDER BY created_at DESC LIMIT 1
                ''', (guild_id, author_id, message_content, one_hour_ago.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
                    
        except Exception as e:
            print(f"중복 메시지 확인 오류: {e}")
            return None

    async def set_new_member_auto_role(self, guild_id: str, role_id: str, enabled: bool = True) -> bool:
        """신규 유저 자동 역할 배정 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 기존 설정이 있는지 확인
                async with db.execute('''
                    SELECT id FROM server_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # 업데이트
                    await db.execute('''
                        UPDATE server_settings 
                        SET new_member_role_id = ?, 
                            auto_assign_new_member = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (role_id, enabled, guild_id))
                else:
                    # 신규 생성
                    await db.execute('''
                        INSERT INTO server_settings 
                        (guild_id, new_member_role_id, auto_assign_new_member)
                        VALUES (?, ?, ?)
                    ''', (guild_id, role_id, enabled))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 신규 유저 자동 역할 설정 실패: {e}")
            return False

    async def get_new_member_auto_role_settings(self, guild_id: str) -> dict:
        """신규 유저 자동 역할 배정 설정 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT new_member_role_id, auto_assign_new_member
                    FROM server_settings 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result:
                        return {
                            'role_id': result[0],
                            'enabled': bool(result[1]) if result[1] is not None else False
                        }
                    else:
                        return {'role_id': None, 'enabled': False}
                        
        except Exception as e:
            print(f"❌ 신규 유저 자동 역할 설정 조회 실패: {e}")
            return {'role_id': None, 'enabled': False}

    async def disable_new_member_auto_role(self, guild_id: str) -> bool:
        """신규 유저 자동 역할 배정 비활성화"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE server_settings 
                    SET auto_assign_new_member = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                ''', (guild_id,))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 신규 유저 자동 역할 배정 비활성화 실패: {e}")
            return False

    async def get_deletable_users_for_autocomplete(self, guild_id: str, search_query: str = "", limit: int = 100):
        """유저삭제 자동완성용 - 관리자 제외, 검색어 필터링"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 관리자 목록 먼저 조회
                admin_user_ids = []
                async with db.execute('''
                    SELECT user_id FROM server_admins 
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,)) as cursor:
                    admin_rows = await cursor.fetchall()
                    admin_user_ids = [row[0] for row in admin_rows]
                
                # 검색어가 있는 경우와 없는 경우 분기
                if search_query:
                    # 검색어가 있으면 DB 레벨에서 필터링
                    search_pattern = f"%{search_query.lower()}%"
                    query = '''
                        SELECT user_id, username, battle_tag, main_position, 
                            current_season_tier, registered_at
                        FROM registered_users 
                        WHERE guild_id = ? 
                        AND is_active = TRUE
                        AND (LOWER(username) LIKE ? OR LOWER(battle_tag) LIKE ?)
                        ORDER BY username ASC
                        LIMIT ?
                    '''
                    params = (guild_id, search_pattern, search_pattern, limit)
                else:
                    # 검색어가 없으면 전체 조회
                    query = '''
                        SELECT user_id, username, battle_tag, main_position, 
                            current_season_tier, registered_at
                        FROM registered_users 
                        WHERE guild_id = ? 
                        AND is_active = TRUE
                        ORDER BY username ASC
                        LIMIT ?
                    '''
                    params = (guild_id, limit)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    users = []
                    for row in rows:
                        user_data = {
                            'user_id': row[0],
                            'username': row[1], 
                            'battle_tag': row[2] or '',
                            'main_position': row[3] or '',
                            'current_season_tier': row[4] or '',
                            'registered_at': row[5]
                        }
                        
                        # 관리자는 제외
                        if user_data['user_id'] not in admin_user_ids:
                            users.append(user_data)
                    
                    return users
                    
        except Exception as e:
            print(f"❌ 삭제 가능 유저 조회 오류: {e}")
            return []
        
    async def get_all_server_admins_for_notification(self, guild_id: str, guild_owner_id: str):
        """알림용 모든 관리자 ID 목록 조회 (서버 소유자 포함)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                admin_ids = set()
                
                # 1. 서버 소유자 추가
                admin_ids.add(guild_owner_id)
                
                # 2. 등록된 관리자들 추가
                async with db.execute('''
                    SELECT user_id FROM server_admins 
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    for row in rows:
                        admin_ids.add(row[0])
                
                return list(admin_ids)
                
        except Exception as e:
            print(f"❌ 관리자 목록 조회 오류: {e}")
            return [guild_owner_id]

    async def create_scrim_recruitment(self, guild_id: str, title: str, description: str, 
                                     scrim_date: datetime, deadline: datetime, 
                                     created_by: str) -> str:
        """새로운 내전 모집 생성"""
        try:
            recruitment_id = str(uuid.uuid4())
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO scrim_recruitments 
                    (id, guild_id, title, description, scrim_date, deadline, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    recruitment_id,
                    guild_id,
                    title,
                    description,
                    scrim_date.isoformat(),
                    deadline.isoformat(),
                    created_by
                ))
                await db.commit()
                
            return recruitment_id
            
        except Exception as e:
            print(f"❌ 내전 모집 생성 실패: {e}")
            raise

    async def update_recruitment_message_id(self, recruitment_id: str, message_id: str, 
                                           channel_id: str) -> bool:
        """모집 메시지 ID 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scrim_recruitments 
                    SET message_id = ?, channel_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (message_id, channel_id, recruitment_id))
                await db.commit()
                
            return True
            
        except Exception as e:
            print(f"❌ 모집 메시지 ID 업데이트 실패: {e}")
            return False

    async def set_recruitment_channel(self, guild_id: str, channel_id: str) -> bool:
        """내전 공지 채널 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 기존 설정이 있는지 확인
                async with db.execute('''
                    SELECT guild_id FROM scrim_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # 업데이트
                    await db.execute('''
                        UPDATE scrim_settings 
                        SET recruitment_channel_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (channel_id, guild_id))
                else:
                    # 신규 생성
                    await db.execute('''
                        INSERT INTO scrim_settings (guild_id, recruitment_channel_id)
                        VALUES (?, ?)
                    ''', (guild_id, channel_id))
                
                await db.commit()
                print(f"✅ 공지 채널 설정 완료: guild_id={guild_id}, channel_id={channel_id}")
                
            return True
            
        except Exception as e:
            print(f"❌ 공지 채널 설정 실패: {e}")
            import traceback
            traceback.print_exc()
            return False


    async def get_recruitment_channel(self, guild_id: str) -> Optional[str]:
        """설정된 내전 공지 채널 ID 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT recruitment_channel_id FROM scrim_settings 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    return result[0] if result and result[0] else None
                    
        except Exception as e:
            print(f"❌ 공지 채널 조회 실패: {e}")
            return None

    async def get_active_recruitments(self, guild_id: str) -> List[Dict]:
        """활성 상태인 내전 모집 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_recruitments 
                    WHERE guild_id = ? AND status = 'active'
                    ORDER BY scrim_date ASC
                ''', (guild_id,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 활성 모집 조회 실패: {e}")
            return []

    async def get_recruitment_by_id(self, recruitment_id: str) -> Optional[Dict]:
        """ID로 특정 모집 정보 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_recruitments WHERE id = ?
                ''', (recruitment_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result:
                        columns = [description[0] for description in cursor.description]
                        return dict(zip(columns, result))
                    
                    return None
                    
        except Exception as e:
            print(f"❌ 모집 정보 조회 실패: {e}")
            return None

    async def add_recruitment_participant(self, recruitment_id: str, user_id: str, 
                                        username: str, status: str) -> bool:
        """모집 참가자 추가/업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO scrim_participants 
                    (recruitment_id, user_id, username, status)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(recruitment_id, user_id) DO UPDATE SET
                        status = excluded.status,
                        username = excluded.username,
                        updated_at = CURRENT_TIMESTAMP
                ''', (recruitment_id, user_id, username, status))
                await db.commit()
                
            return True
            
        except Exception as e:
            print(f"❌ 참가자 추가/업데이트 실패: {e}")
            return False

    async def get_recruitment_participants(self, recruitment_id: str) -> List[Dict]:
        """특정 모집의 참가자 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_participants 
                    WHERE recruitment_id = ?
                    ORDER BY joined_at ASC
                ''', (recruitment_id,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 참가자 목록 조회 실패: {e}")
            return []

    async def close_recruitment(self, recruitment_id: str) -> bool:
        """모집 마감 처리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scrim_recruitments 
                    SET status = 'closed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (recruitment_id,))
                await db.commit()
                
            return True
            
        except Exception as e:
            print(f"❌ 모집 마감 처리 실패: {e}")
            return False

    async def get_expired_recruitments(self) -> List[Dict]:
        """마감시간이 지난 활성 모집들 조회"""
        try:
            current_time = datetime.now().isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_recruitments 
                    WHERE status = 'active' AND deadline < ?
                ''', (current_time,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 만료된 모집 조회 실패: {e}")
            return []

    async def cancel_recruitment(self, recruitment_id: str) -> bool:
        """모집 취소 처리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scrim_recruitments 
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status = 'active'
                ''', (recruitment_id,))
                
                result = await db.execute('SELECT changes()')
                changes = await result.fetchone()
                
                await db.commit()
                
                return changes[0] > 0  # 실제로 업데이트된 행이 있는지 확인
                
        except Exception as e:
            print(f"❌ 모집 취소 처리 실패: {e}")
            return False

    async def get_user_participation_status(self, recruitment_id: str, user_id: str) -> Optional[str]:
        """특정 사용자의 특정 모집 참가 상태 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT status FROM scrim_participants 
                    WHERE recruitment_id = ? AND user_id = ?
                ''', (recruitment_id, user_id)) as cursor:
                    result = await cursor.fetchone()
                    
                    return result[0] if result else None
                    
        except Exception as e:
            print(f"❌ 사용자 참가 상태 조회 실패: {e}")
            return None

    async def get_recruitment_stats(self, guild_id: str) -> Dict:
        """서버의 내전 모집 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 전체 모집 수
                async with db.execute('''
                    SELECT COUNT(*) FROM scrim_recruitments WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    total_recruitments = (await cursor.fetchone())[0]
                
                # 활성 모집 수
                async with db.execute('''
                    SELECT COUNT(*) FROM scrim_recruitments 
                    WHERE guild_id = ? AND status = 'active'
                ''', (guild_id,)) as cursor:
                    active_recruitments = (await cursor.fetchone())[0]
                
                # 완료된 모집 수  
                async with db.execute('''
                    SELECT COUNT(*) FROM scrim_recruitments 
                    WHERE guild_id = ? AND status = 'closed'
                ''', (guild_id,)) as cursor:
                    closed_recruitments = (await cursor.fetchone())[0]
                
                # 취소된 모집 수
                async with db.execute('''
                    SELECT COUNT(*) FROM scrim_recruitments 
                    WHERE guild_id = ? AND status = 'cancelled'
                ''', (guild_id,)) as cursor:
                    cancelled_recruitments = (await cursor.fetchone())[0]
                
                # 총 참가자 수 (중복 제거)
                async with db.execute('''
                    SELECT COUNT(DISTINCT user_id) FROM scrim_participants 
                    WHERE recruitment_id IN (
                        SELECT id FROM scrim_recruitments WHERE guild_id = ?
                    )
                ''', (guild_id,)) as cursor:
                    unique_participants = (await cursor.fetchone())[0]
                
                return {
                    'total_recruitments': total_recruitments,
                    'active_recruitments': active_recruitments,
                    'closed_recruitments': closed_recruitments,
                    'cancelled_recruitments': cancelled_recruitments,
                    'unique_participants': unique_participants
                }
                
        except Exception as e:
            print(f"❌ 모집 통계 조회 실패: {e}")
            return {}

    async def get_user_recruitment_history(self, guild_id: str, user_id: str) -> List[Dict]:
        """특정 사용자의 모집 참가 이력"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT r.title, r.scrim_date, r.status as recruitment_status,
                        p.status as participation_status, p.joined_at
                    FROM scrim_recruitments r
                    JOIN scrim_participants p ON r.id = p.recruitment_id
                    WHERE r.guild_id = ? AND p.user_id = ?
                    ORDER BY r.scrim_date DESC
                    LIMIT 20
                ''', (guild_id, user_id)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 사용자 참가 이력 조회 실패: {e}")
            return []

    async def cleanup_old_recruitments(self, days_old: int = 30) -> int:
        """오래된 모집 데이터 정리"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # 오래된 참가자 데이터 삭제
                await db.execute('''
                    DELETE FROM scrim_participants 
                    WHERE recruitment_id IN (
                        SELECT id FROM scrim_recruitments 
                        WHERE created_at < ? AND status IN ('closed', 'cancelled')
                    )
                ''', (cutoff_date,))
                
                # 오래된 모집 데이터 삭제
                result = await db.execute('''
                    DELETE FROM scrim_recruitments 
                    WHERE created_at < ? AND status IN ('closed', 'cancelled')
                ''', (cutoff_date,))
                
                deleted_count = result.rowcount
                await db.commit()
                
                print(f"✅ {deleted_count}개의 오래된 모집 데이터 정리 완료")
                return deleted_count
                
        except Exception as e:
            print(f"❌ 오래된 데이터 정리 실패: {e}")
            return 0

    async def get_popular_participation_times(self, guild_id: str) -> Dict:
        """인기 있는 참가 시간대 분석"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 시간대별 참가자 수 통계
                async with db.execute('''
                    SELECT 
                        CASE 
                            WHEN CAST(strftime('%H', r.scrim_date) AS INTEGER) BETWEEN 0 AND 5 THEN '새벽 (0-5시)'
                            WHEN CAST(strftime('%H', r.scrim_date) AS INTEGER) BETWEEN 6 AND 11 THEN '오전 (6-11시)'
                            WHEN CAST(strftime('%H', r.scrim_date) AS INTEGER) BETWEEN 12 AND 17 THEN '오후 (12-17시)'
                            WHEN CAST(strftime('%H', r.scrim_date) AS INTEGER) BETWEEN 18 AND 23 THEN '저녁 (18-23시)'
                        END as time_period,
                        COUNT(p.user_id) as participant_count,
                        COUNT(DISTINCT r.id) as recruitment_count
                    FROM scrim_recruitments r
                    LEFT JOIN scrim_participants p ON r.id = p.recruitment_id AND p.status = 'joined'
                    WHERE r.guild_id = ? AND r.status = 'closed'
                    GROUP BY time_period
                ''', (guild_id,)) as cursor:
                    results = await cursor.fetchall()
                    
                    stats = {}
                    for time_period, participant_count, recruitment_count in results:
                        if time_period:  # None 체크
                            stats[time_period] = {
                                'participant_count': participant_count,
                                'recruitment_count': recruitment_count,
                                'avg_participants': round(participant_count / recruitment_count, 1) if recruitment_count > 0 else 0
                            }
                    
                    return stats
                    
        except Exception as e:
            print(f"❌ 시간대 분석 실패: {e}")
            return {}

    async def get_server_admins(self, guild_id: str) -> List[Dict]:
        """서버의 등록된 관리자 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT user_id, username, added_at FROM server_admins 
                    WHERE guild_id = ?
                    ORDER BY added_at ASC
                ''', (guild_id,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 서버 관리자 목록 조회 실패: {e}")
            return []

    async def get_recruitment_detailed_stats(self, recruitment_id: str) -> Dict:
        """특정 모집의 상세 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 기본 모집 정보
                async with db.execute('''
                    SELECT * FROM scrim_recruitments WHERE id = ?
                ''', (recruitment_id,)) as cursor:
                    recruitment_data = await cursor.fetchone()
                    if not recruitment_data:
                        return {}
                    
                    columns = [description[0] for description in cursor.description]
                    recruitment = dict(zip(columns, recruitment_data))
                
                # 참가자 통계
                async with db.execute('''
                    SELECT 
                        status,
                        COUNT(*) as count,
                        GROUP_CONCAT(username, ', ') as users
                    FROM scrim_participants 
                    WHERE recruitment_id = ?
                    GROUP BY status
                ''', (recruitment_id,)) as cursor:
                    participant_stats = await cursor.fetchall()
                
                # 시간별 참가 패턴
                async with db.execute('''
                    SELECT 
                        strftime('%H', joined_at) as hour,
                        COUNT(*) as registrations
                    FROM scrim_participants 
                    WHERE recruitment_id = ?
                    GROUP BY strftime('%H', joined_at)
                    ORDER BY hour
                ''', (recruitment_id,)) as cursor:
                    hourly_stats = await cursor.fetchall()
                
                # 결과 구성
                stats = recruitment.copy()
                stats['participant_stats'] = {
                    stat[0]: {'count': stat[1], 'users': stat[2].split(', ') if stat[2] else []}
                    for stat in participant_stats
                }
                stats['hourly_registration'] = [
                    {'hour': stat[0], 'count': stat[1]} for stat in hourly_stats
                ]
                
                return stats
                
        except Exception as e:
            print(f"❌ 모집 상세 통계 조회 실패: {e}")
            return {}

    async def get_recruitment_summary_for_admin(self, guild_id: str, days: int = 7) -> Dict:
        """관리자용 최근 모집 요약"""
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # 최근 모집들
                async with db.execute('''
                    SELECT 
                        r.*,
                        COUNT(CASE WHEN p.status = 'joined' THEN 1 END) as joined_count,
                        COUNT(CASE WHEN p.status = 'declined' THEN 1 END) as declined_count,
                        COUNT(p.user_id) as total_responses
                    FROM scrim_recruitments r
                    LEFT JOIN scrim_participants p ON r.id = p.recruitment_id
                    WHERE r.guild_id = ? AND r.created_at > ?
                    GROUP BY r.id
                    ORDER BY r.created_at DESC
                    LIMIT 10
                ''', (guild_id, cutoff_date)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    recent_recruitments = [dict(zip(columns, row)) for row in results]
                
                # 전체 통계
                async with db.execute('''
                    SELECT 
                        COUNT(*) as total_recruitments,
                        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
                        COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed_count,
                        COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count
                    FROM scrim_recruitments
                    WHERE guild_id = ? AND created_at > ?
                ''', (guild_id, cutoff_date)) as cursor:
                    overall_stats = await cursor.fetchone()
                
                return {
                    'recent_recruitments': recent_recruitments,
                    'overall_stats': {
                        'total': overall_stats[0],
                        'active': overall_stats[1], 
                        'closed': overall_stats[2],
                        'cancelled': overall_stats[3]
                    },
                    'period_days': days
                }
                
        except Exception as e:
            print(f"❌ 관리자용 모집 요약 조회 실패: {e}")
            return {}

    async def update_recruitment_notification_sent(self, recruitment_id: str, 
                                                notification_type: str = 'closed') -> bool:
        """모집 알림 발송 기록"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 알림 발송 기록용 컬럼이 없다면 추가하는 로직도 포함
                try:
                    await db.execute('''
                        ALTER TABLE scrim_recruitments 
                        ADD COLUMN notifications_sent TEXT DEFAULT ''
                    ''')
                except:
                    pass  # 컬럼이 이미 존재하는 경우
                
                # 기존 알림 기록 조회
                async with db.execute('''
                    SELECT notifications_sent FROM scrim_recruitments WHERE id = ?
                ''', (recruitment_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result:
                        existing_notifications = result[0] or ''
                        new_notifications = f"{existing_notifications},{notification_type}" if existing_notifications else notification_type
                        
                        await db.execute('''
                            UPDATE scrim_recruitments 
                            SET notifications_sent = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE id = ?
                        ''', (new_notifications, recruitment_id))
                        
                        await db.commit()
                        return True
                
                return False
                
        except Exception as e:
            print(f"❌ 알림 발송 기록 실패: {e}")
            return False

    async def get_recruitment_participation_timeline(self, recruitment_id: str) -> List[Dict]:
        """모집 참가 신청 시간순 타임라인"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        user_id, username, status, joined_at, updated_at
                    FROM scrim_participants 
                    WHERE recruitment_id = ?
                    ORDER BY joined_at ASC
                ''', (recruitment_id,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    timeline = []
                    for row in results:
                        event = dict(zip(columns, row))
                        # 참가 상태 변경 이력도 추가
                        if event['joined_at'] != event['updated_at']:
                            event['status_changed'] = True
                        else:
                            event['status_changed'] = False
                        timeline.append(event)
                    
                    return timeline
                    
        except Exception as e:
            print(f"❌ 참가 타임라인 조회 실패: {e}")
            return []

    async def schedule_recruitment_reminder(self, recruitment_id: str, remind_before_minutes: int = 60):
        """모집 마감 전 리마인더 스케줄링 (향후 확장용)"""
        try:
            # 향후 리마인더 기능 구현 시 사용할 메소드
            # 현재는 기본 구조만 제공
            async with aiosqlite.connect(self.db_path) as db:
                # 리마인더 테이블이 필요하면 생성
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS recruitment_reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        recruitment_id TEXT NOT NULL,
                        remind_at TEXT NOT NULL,
                        status TEXT DEFAULT 'pending',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (recruitment_id) REFERENCES scrim_recruitments(id)
                    )
                ''')
                
                # 리마인더 시간 계산 및 저장
                recruitment = await self.get_recruitment_by_id(recruitment_id)
                if recruitment:
                    from datetime import datetime, timedelta
                    deadline = datetime.fromisoformat(recruitment['deadline'])
                    remind_at = deadline - timedelta(minutes=remind_before_minutes)
                    
                    await db.execute('''
                        INSERT INTO recruitment_reminders (recruitment_id, remind_at)
                        VALUES (?, ?)
                    ''', (recruitment_id, remind_at.isoformat()))
                    
                    await db.commit()
                    return True
                
                return False
                
        except Exception as e:
            print(f"❌ 리마인더 스케줄링 실패: {e}")
            return False

    async def set_bamboo_channel(self, guild_id: str, channel_id: str) -> bool:
        """대나무숲 채널 ID 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 기존 설정이 있는지 확인
                async with db.execute('''
                    SELECT guild_id FROM server_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    exists = await cursor.fetchone()
                
                if exists:
                    # 기존 설정 업데이트
                    await db.execute('''
                        UPDATE server_settings 
                        SET bamboo_channel_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (channel_id, guild_id))
                else:
                    # 새 설정 추가
                    await db.execute('''
                        INSERT INTO server_settings (guild_id, bamboo_channel_id)
                        VALUES (?, ?)
                    ''', (guild_id, channel_id))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 대나무숲 채널 설정 실패: {e}")
            return False

    async def get_bamboo_channel(self, guild_id: str) -> str:
        """대나무숲 채널 ID 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT bamboo_channel_id FROM server_settings 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[0]:
                        return result[0]
                    return None
                    
        except Exception as e:
            print(f"❌ 대나무숲 채널 조회 실패: {e}")
            return None

    async def remove_bamboo_channel(self, guild_id: str) -> bool:
        """대나무숲 채널 설정 제거"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE server_settings 
                    SET bamboo_channel_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                ''', (guild_id,))
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 대나무숲 채널 설정 제거 실패: {e}")
            return False

    async def get_completed_recruitments(self, guild_id: str) -> List[Dict]:
        """마감된 내전 모집 목록 조회 (참가자 수 포함)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        r.id,
                        r.title,
                        r.description,
                        r.scrim_date,
                        r.deadline,
                        r.created_by,
                        COUNT(p.user_id) as participant_count
                    FROM scrim_recruitments r
                    LEFT JOIN scrim_participants p ON r.id = p.recruitment_id 
                        AND p.status = 'joined'
                    WHERE r.guild_id = ? 
                        AND r.status = 'closed'
                        AND datetime(r.deadline) <= datetime('now', 'localtime')
                    GROUP BY r.id
                    ORDER BY r.scrim_date DESC
                    LIMIT 10
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'id': row[0],
                            'title': row[1],
                            'description': row[2],
                            'scrim_date': row[3],
                            'deadline': row[4],
                            'created_by': row[5],
                            'participant_count': row[6]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"마감된 모집 조회 실패: {e}")
            return []
            
    async def save_match_result(self, match_data: Dict) -> str:
        """매치 결과를 데이터베이스에 저장 (맵 정보 포함)"""
        try:
            match_id = str(uuid.uuid4())
            
            async with aiosqlite.connect(self.db_path) as db:
                # 🆕 맵 정보 추출
                map_name = match_data.get('map_name')
                map_type = match_data.get('map_type')
                
                # 매치 기본 정보 저장 (맵 정보 포함)
                await db.execute('''
                    INSERT INTO match_results (
                        id, recruitment_id, match_number, winning_team, 
                        created_by, guild_id, match_date, map_name, map_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    match_data['recruitment_id'],
                    match_data['match_number'],
                    match_data['winner'],
                    match_data['created_by'],
                    match_data['guild_id'],
                    datetime.now().isoformat(),
                    map_name,
                    map_type
                ))
                
                # 참가자별 세부 정보 저장
                for team_key in ['team_a', 'team_b']:
                    team_data = match_data[team_key]
                    positions = match_data[f'{team_key}_positions']
                    is_winning_team = (match_data['winner'] == team_key)
                    
                    for participant in team_data:
                        user_id = participant['user_id']
                        position = positions.get(user_id, '미설정')  # 포지션 정보가 없을 경우 기본값
                        
                        await db.execute('''
                            INSERT INTO match_participants (
                                match_id, user_id, username, team, position, won
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            match_id,
                            user_id,
                            participant['username'],
                            team_key,
                            position,
                            is_winning_team
                        ))
                
                await db.commit()
                return match_id
                
        except Exception as e:
            print(f"❌ 매치 저장 실패: {e}")
            raise

    async def _get_registered_user_ids(self, guild_id: str) -> set:
        """등록된 유저 ID 목록을 Set으로 반환"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT user_id FROM registered_users 
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return {row[0] for row in rows}
        except Exception as e:
            print(f"❌ 등록된 유저 ID 조회 실패: {e}")
            return set()

    async def update_user_statistics(self, guild_id: str, match_results: List[Dict]):
        """여러 매치 결과를 기반으로 사용자 통계 업데이트 (등록된 유저만)
        
        Args:
            guild_id: 서버 ID
            match_results: 매치 결과 데이터 리스트
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 🔍 등록된 유저 ID 목록 조회 (한 번만)
                registered_user_ids = await self._get_registered_user_ids(guild_id)
                
                if not registered_user_ids:
                    print("⚠️ 등록된 유저가 없습니다.")
                    return
                
                skipped_users = [] 
                
                for match_data in match_results:
                    for team_key in ['team_a', 'team_b']:
                        team_data = match_data[team_key]
                        positions = match_data[f'{team_key}_positions']
                        is_winning_team = (match_data['winner'] == team_key)
                        
                        for participant in team_data:
                            user_id = participant['user_id']
                            
                            if user_id not in registered_user_ids:
                                skipped_users.append({
                                    'username': participant['username'],
                                    'user_id': user_id
                                })
                                print(f"⚠️ 미등록 유저 통계 제외: {participant['username']} ({user_id})")
                                continue
                            
                            position = positions[user_id]
                            
                            await self._update_single_user_stats(
                                db, guild_id, user_id, position, is_winning_team
                            )
                
                await db.commit()
                
                # 결과 요약 로그
                registered_count = len(registered_user_ids)
                skipped_count = len(set(u['user_id'] for u in skipped_users))
                print(f"✅ 통계 업데이트 완료 - 등록 유저: {registered_count}명 반영, 외부 유저: {skipped_count}명 제외")
                
        except Exception as e:
            print(f"❌ 통계 업데이트 실패: {e}")
            raise

    async def _update_single_user_stats(self, db, guild_id: str, user_id: str, position: str, won: bool):
        """개별 사용자 통계 업데이트"""
        # 기존 통계 조회
        async with db.execute('''
            SELECT total_games, total_wins, tank_games, tank_wins, 
                dps_games, dps_wins, support_games, support_wins
            FROM user_statistics
            WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id)) as cursor:
            existing = await cursor.fetchone()
        
        if existing:
            # 기존 데이터 업데이트
            total_games, total_wins, tank_games, tank_wins = existing[:4]
            dps_games, dps_wins, support_games, support_wins = existing[4:]
            
            # 전체 통계 업데이트
            total_games += 1
            if won:
                total_wins += 1
            
            # 포지션별 통계 업데이트
            if position == '탱커':
                tank_games += 1
                if won:
                    tank_wins += 1
            elif position == '딜러':
                dps_games += 1
                if won:
                    dps_wins += 1
            elif position == '힐러':
                support_games += 1
                if won:
                    support_wins += 1
            
            await db.execute('''
                UPDATE user_statistics SET
                    total_games = ?, total_wins = ?,
                    tank_games = ?, tank_wins = ?,
                    dps_games = ?, dps_wins = ?,
                    support_games = ?, support_wins = ?,
                    last_updated = ?
                WHERE user_id = ? AND guild_id = ?
            ''', (
                total_games, total_wins, tank_games, tank_wins,
                dps_games, dps_wins, support_games, support_wins,
                datetime.now().isoformat(), user_id, guild_id
            ))
        else:
            # 새 데이터 생성
            stats = {
                'total_games': 1, 'total_wins': 1 if won else 0,
                'tank_games': 0, 'tank_wins': 0,
                'dps_games': 0, 'dps_wins': 0,
                'support_games': 0, 'support_wins': 0
            }
            
            if position == '탱커':
                stats['tank_games'] = 1
                stats['tank_wins'] = 1 if won else 0
            elif position == '딜러':
                stats['dps_games'] = 1
                stats['dps_wins'] = 1 if won else 0
            elif position == '힐러':
                stats['support_games'] = 1
                stats['support_wins'] = 1 if won else 0
            
            await db.execute('''
                INSERT INTO user_statistics (
                    user_id, guild_id, total_games, total_wins,
                    tank_games, tank_wins, dps_games, dps_wins,
                    support_games, support_wins, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, guild_id, stats['total_games'], stats['total_wins'],
                stats['tank_games'], stats['tank_wins'], stats['dps_games'], stats['dps_wins'],
                stats['support_games'], stats['support_wins'], datetime.now().isoformat()
            ))

    async def get_detailed_user_stats(self, user_id: str, guild_id: str = None) -> Dict:
        """사용자의 상세 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                query = '''
                    SELECT total_games, total_wins, tank_games, tank_wins,
                        dps_games, dps_wins, support_games, support_wins
                    FROM user_statistics
                    WHERE user_id = ?
                '''
                params = [user_id]
                
                if guild_id:
                    query += ' AND guild_id = ?'
                    params.append(guild_id)
                
                async with db.execute(query, params) as cursor:
                    result = await cursor.fetchone()
                    
                    if not result:
                        return None
                    
                    total_games, total_wins, tank_games, tank_wins = result[:4]
                    dps_games, dps_wins, support_games, support_wins = result[4:]
                    
                    return {
                        'total_games': total_games,
                        'wins': total_wins,
                        'losses': total_games - total_wins,
                        'tank_games': tank_games,
                        'tank_wins': tank_wins,
                        'tank_winrate': (tank_wins / tank_games * 100) if tank_games > 0 else 0,
                        'dps_games': dps_games,
                        'dps_wins': dps_wins,
                        'dps_winrate': (dps_wins / dps_games * 100) if dps_games > 0 else 0,
                        'support_games': support_games,
                        'support_wins': support_wins,
                        'support_winrate': (support_wins / support_games * 100) if support_games > 0 else 0,
                        'overall_winrate': (total_wins / total_games * 100) if total_games > 0 else 0
                    }
                    
        except Exception as e:
            print(f"사용자 통계 조회 실패: {e}")
            return None

    async def get_recent_matches(self, user_id: str, guild_id: str, limit: int = 5) -> List[Dict]:
        """사용자의 최근 경기 기록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT mr.match_date, mp.position, mp.won, mr.match_number,
                        sr.title as scrim_title
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    JOIN scrim_recruitments sr ON mr.recruitment_id = sr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ?
                    ORDER BY mr.match_date DESC
                    LIMIT ?
                ''', (user_id, guild_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'match_date': row[0],
                            'position': row[1],
                            'won': bool(row[2]),
                            'match_number': row[3],
                            'scrim_title': row[4]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"최근 경기 조회 실패: {e}")
            return []

    async def get_user_server_rank(self, user_id: str, guild_id: str, position: str = "all") -> Dict:
        """특정 사용자의 서버 내 순위 조회 (포지션별 순위 지원)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 포지션별 게임 수와 승수 컬럼 선택
                if position == "tank":
                    games_col = "tank_games"
                    wins_col = "tank_wins"
                elif position == "dps":
                    games_col = "dps_games"
                    wins_col = "dps_wins"
                elif position == "support":
                    games_col = "support_games"
                    wins_col = "support_wins"
                else:  # all
                    games_col = "total_games"
                    wins_col = "total_wins"
                
                # 전체 랭킹에서 해당 사용자 순위 찾기
                async with db.execute(f'''
                    WITH ranked_users AS (
                        SELECT user_id,
                            ROW_NUMBER() OVER (
                                ORDER BY 
                                    CASE WHEN {games_col} > 0 
                                            THEN {wins_col} * 100.0 / {games_col} 
                                            ELSE 0 END DESC,
                                    {games_col} DESC
                            ) as rank
                        FROM user_statistics
                        WHERE guild_id = ? AND {games_col} >= 5
                    ),
                    user_stats AS (
                        SELECT COUNT(*) as total_users
                        FROM user_statistics
                        WHERE guild_id = ? AND {games_col} >= 5
                    )
                    SELECT ru.rank, us.total_users
                    FROM ranked_users ru, user_stats us
                    WHERE ru.user_id = ?
                ''', (guild_id, guild_id, user_id)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result:
                        rank, total_users = result
                        percentile = (rank / total_users) * 100
                        
                        return {
                            'rank': rank,
                            'total_users': total_users,
                            'percentile': round(percentile, 1)
                        }
                    
                    return None
                    
        except Exception as e:
            print(f"개인 랭킹 조회 실패: {e}")
            return None

    async def get_head_to_head(self, user1_id: str, user2_id: str, guild_id: str) -> Dict:
        """두 사용자 간 대전 기록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        SUM(CASE WHEN mp1.won = 1 AND mp2.won = 0 THEN 1 ELSE 0 END) as user1_wins,
                        SUM(CASE WHEN mp1.won = 0 AND mp2.won = 1 THEN 1 ELSE 0 END) as user2_wins,
                        COUNT(*) as total_matches
                    FROM match_participants mp1
                    JOIN match_participants mp2 ON mp1.match_id = mp2.match_id
                    JOIN match_results mr ON mp1.match_id = mr.id
                    WHERE mp1.user_id = ?      
                        AND mp2.user_id = ?         
                        AND mp1.user_id != mp2.user_id 
                        AND mp1.team != mp2.team    
                        AND mr.guild_id = ?  
                ''', (user1_id, user2_id, guild_id)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[2] > 0:
                        return {
                            'user1_wins': result[0] or 0,
                            'user2_wins': result[1] or 0,
                            'total_matches': result[2],
                            'wins': result[0] or 0,   
                            'losses': result[1] or 0  
                        }
                    
                    return None
                    
        except Exception as e:
            print(f"Head-to-Head 조회 실패: {e}")
            return None

    async def finalize_session_statistics(self, guild_id: str, completed_matches: List[Dict]):
        """세션 완료 후 모든 통계 일괄 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 트랜잭션으로 일괄 처리
                await db.execute('BEGIN TRANSACTION')
                
                try:
                    for match_data in completed_matches:
                        # 매치 저장
                        match_id = await self.save_match_result(match_data)
                        
                        # 개별 통계 업데이트
                        for team_key in ['team_a', 'team_b']:
                            team_data = match_data[team_key]
                            positions = match_data[f'{team_key}_positions']
                            is_winning_team = (match_data['winner'] == team_key)
                            
                            for participant in team_data:
                                user_id = participant['user_id']
                                position = positions[user_id]
                                
                                await self._update_single_user_stats(
                                    db, guild_id, user_id, position, is_winning_team
                                )
                    
                    await db.execute('COMMIT')
                    return True
                    
                except Exception as e:
                    await db.execute('ROLLBACK')
                    raise e
                    
        except Exception as e:
            print(f"세션 통계 완료 실패: {e}")
            return False

    async def get_max_match_number(self, recruitment_id: str) -> Optional[int]:
        """특정 모집의 최대 경기번호 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT MAX(match_number) FROM match_results 
                    WHERE recruitment_id = ?
                ''', (recruitment_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result[0] is not None else None
                    
        except Exception as e:
            print(f"최대 경기번호 조회 실패: {e}")
            return None

    async def get_user_map_type_stats(self, user_id: str, guild_id: str) -> List[Dict]:
        """사용자의 맵 타입별 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL
                    GROUP BY mr.map_type
                    HAVING COUNT(*) >= 3  -- 최소 3경기 이상
                    ORDER BY winrate DESC
                ''', (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'map_type': row[0],
                            'games': row[1], 
                            'wins': row[2],
                            'winrate': row[3]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"맵 타입별 통계 조회 실패: {e}")
            return []

    async def get_user_best_worst_maps(self, user_id: str, guild_id: str) -> Dict:
        """사용자의 최고/최저 승률 맵 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mr.map_name,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_name IS NOT NULL
                    GROUP BY mr.map_name
                    HAVING COUNT(*) >= 3  -- 최소 3경기 이상
                    ORDER BY winrate DESC
                ''', (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    if not rows:
                        return {}
                    
                    # 최고/최저 맵 추출
                    best_map = rows[0]  # 첫 번째 = 최고 승률
                    worst_map = rows[-1]  # 마지막 = 최저 승률
                    
                    result = {
                        'best_map': {
                            'name': best_map[0],
                            'games': best_map[1],
                            'wins': best_map[2], 
                            'winrate': best_map[3]
                        }
                    }
                    
                    # 최고와 최저가 다른 경우에만 최저 맵 추가
                    if len(rows) > 1 and best_map[0] != worst_map[0]:
                        result['worst_map'] = {
                            'name': worst_map[0],
                            'games': worst_map[1],
                            'wins': worst_map[2],
                            'winrate': worst_map[3]
                        }
                    
                    return result
                    
        except Exception as e:
            print(f"최고/최저 맵 조회 실패: {e}")
            return {}

    async def get_user_position_map_stats(self, user_id: str, guild_id: str) -> List[Dict]:
        """사용자의 포지션-맵타입 조합별 성과 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mp.position,
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL 
                        AND mp.position IS NOT NULL
                    GROUP BY mp.position, mr.map_type
                    HAVING COUNT(*) >= 3  -- 최소 3경기 이상
                    ORDER BY mp.position, winrate DESC
                ''', (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'position': row[0],
                            'map_type': row[1],
                            'games': row[2],
                            'wins': row[3],
                            'winrate': row[4]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"포지션-맵 조합 통계 조회 실패: {e}")
            return []

    async def get_server_map_type_rankings(self, guild_id: str, map_type: str, min_games: int = 3) -> List[Dict]:
        """서버 맵 타입별 랭킹 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mp.user_id,
                        mp.username,
                        ru.current_season_tier,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    LEFT JOIN registered_users ru ON mp.user_id = ru.user_id AND mr.guild_id = ru.guild_id
                    WHERE mr.guild_id = ? AND mr.map_type = ?
                    GROUP BY mp.user_id, mp.username
                    HAVING COUNT(*) >= ?
                    ORDER BY winrate DESC, games DESC
                    LIMIT 50
                ''', (guild_id, map_type, min_games)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'tier': row[2],
                            'games': row[3],
                            'wins': row[4],
                            'winrate': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"맵 타입별 랭킹 조회 실패: {e}")
            return []

    async def get_server_specific_map_rankings(self, guild_id: str, map_name: str, min_games: int = 3) -> List[Dict]:
        """서버 특정 맵별 랭킹 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mp.user_id,
                        mp.username,
                        ru.current_season_tier,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    LEFT JOIN registered_users ru ON mp.user_id = ru.user_id AND mr.guild_id = ru.guild_id
                    WHERE mr.guild_id = ? AND mr.map_name = ?
                    GROUP BY mp.user_id, mp.username
                    HAVING COUNT(*) >= ?
                    ORDER BY winrate DESC, games DESC
                    LIMIT 50
                ''', (guild_id, map_name, min_games)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1], 
                            'tier': row[2],
                            'games': row[3],
                            'wins': row[4],
                            'winrate': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"특정 맵 랭킹 조회 실패: {e}")
            return []

    async def get_server_rankings(self, guild_id: str, sort_by: str = "winrate", 
                                position: str = "all", min_games: int = 5) -> List[Dict]:
        """서버 내 사용자 랭킹 조회 (포지션별 데이터 반환 지원)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 맵 타입별 정렬인지 확인
                if sort_by.endswith('_winrate'):
                    map_type_name = sort_by.replace('_winrate', '')
                    # 맵 타입명 매핑
                    map_type_map = {
                        'escort': '호위',
                        'control': '쟁탈', 
                        'hybrid': '혼합',
                        'push': '밀기',
                        'flashpoint': '플래시포인트',
                        'clash': '격돌'
                    }
                    
                    if map_type_name in map_type_map:
                        return await self.get_server_map_type_rankings(
                            guild_id, map_type_map[map_type_name], min_games=3
                        )
                
                # 포지션별 게임 수와 승수 컬럼 선택
                if position == "tank":
                    games_col = "us.tank_games"
                    wins_col = "us.tank_wins"
                elif position == "dps":
                    games_col = "us.dps_games"
                    wins_col = "us.dps_wins"
                elif position == "support":
                    games_col = "us.support_games"
                    wins_col = "us.support_wins"
                else:  # all
                    games_col = "us.total_games"
                    wins_col = "us.total_wins"
                
                # 기본 쿼리
                base_query = f'''
                    SELECT 
                        us.user_id,
                        ru.username,
                        ru.current_season_tier,
                        {games_col} as games,
                        {wins_col} as wins,
                        ROUND({wins_col} * 100.0 / {games_col}, 1) as winrate
                    FROM user_statistics us
                    LEFT JOIN registered_users ru ON us.user_id = ru.user_id AND us.guild_id = ru.guild_id
                    WHERE us.guild_id = ? AND {games_col} >= ?
                '''
                
                params = [guild_id, min_games]
                
                # 정렬 기준 적용
                if sort_by == "winrate":
                    base_query += " ORDER BY winrate DESC, games DESC"
                elif sort_by == "games":
                    base_query += " ORDER BY games DESC, winrate DESC"
                elif sort_by == "wins":
                    base_query += " ORDER BY wins DESC, winrate DESC"
                
                base_query += " LIMIT 50"
                
                async with db.execute(base_query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1] or 'Unknown',
                            'tier': row[2],
                            'total_games': row[3],  # 실제로는 포지션별 게임 수
                            'wins': row[4],  # 실제로는 포지션별 승수
                            'winrate': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"서버 랭킹 조회 실패: {e}")
            return []

    async def get_server_map_popularity(self, guild_id: str, map_type: str = "all", limit: int = 10) -> List[Dict]:
        """서버 인기 맵 랭킹 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if map_type == "all":
                    query = '''
                        SELECT 
                            map_name,
                            map_type,
                            COUNT(*) as play_count,
                            ROUND(COUNT(*) * 100.0 / (
                                SELECT COUNT(*) FROM match_results 
                                WHERE guild_id = ? AND map_name IS NOT NULL
                            ), 1) as play_percentage
                        FROM match_results 
                        WHERE guild_id = ? AND map_name IS NOT NULL
                        GROUP BY map_name, map_type
                        ORDER BY play_count DESC
                        LIMIT ?
                    '''
                    params = (guild_id, guild_id, limit)
                else:
                    query = '''
                        SELECT 
                            map_name,
                            map_type,
                            COUNT(*) as play_count,
                            ROUND(COUNT(*) * 100.0 / (
                                SELECT COUNT(*) FROM match_results 
                                WHERE guild_id = ? AND map_type = ? AND map_name IS NOT NULL
                            ), 1) as play_percentage
                        FROM match_results 
                        WHERE guild_id = ? AND map_type = ? AND map_name IS NOT NULL
                        GROUP BY map_name, map_type
                        ORDER BY play_count DESC
                        LIMIT ?
                    '''
                    params = (guild_id, map_type, guild_id, map_type, limit)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'map_name': row[0],
                            'map_type': row[1], 
                            'play_count': row[2],
                            'play_percentage': row[3]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"서버 맵 인기도 조회 실패: {e}")
            return []

    async def get_server_map_balance(self, guild_id: str, min_games: int = 3) -> List[Dict]:
        """서버 맵별 밸런스 분석 (A팀 vs B팀 승률)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        map_name,
                        map_type,
                        COUNT(*) as total_games,
                        SUM(CASE WHEN winning_team = 'team_a' THEN 1 ELSE 0 END) as team_a_wins,
                        SUM(CASE WHEN winning_team = 'team_b' THEN 1 ELSE 0 END) as team_b_wins,
                        ROUND(SUM(CASE WHEN winning_team = 'team_a' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as team_a_winrate,
                        ROUND(SUM(CASE WHEN winning_team = 'team_b' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as team_b_winrate,
                        ABS(50.0 - (SUM(CASE WHEN winning_team = 'team_a' THEN 1 ELSE 0 END) * 100.0 / COUNT(*))) as balance_score
                    FROM match_results 
                    WHERE guild_id = ? AND map_name IS NOT NULL
                    GROUP BY map_name, map_type
                    HAVING COUNT(*) >= ?
                    ORDER BY balance_score ASC  -- 0에 가까울수록 균형잡힘
                ''', (guild_id, min_games)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'map_name': row[0],
                            'map_type': row[1],
                            'total_games': row[2],
                            'team_a_wins': row[3],
                            'team_b_wins': row[4],
                            'team_a_winrate': row[5],
                            'team_b_winrate': row[6],
                            'balance_score': row[7],
                            'balance_rating': self._get_balance_rating(row[7])
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"서버 맵 밸런스 조회 실패: {e}")
            return []

    async def get_server_map_meta(self, guild_id: str, min_games: int = 5) -> List[Dict]:
        """서버 맵 메타 분석 (맵별 포지션 승률)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mr.map_name,
                        mr.map_type,
                        mp.position,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mr.guild_id = ? AND mr.map_name IS NOT NULL AND mp.position IS NOT NULL
                    GROUP BY mr.map_name, mr.map_type, mp.position
                    HAVING COUNT(*) >= ?
                    ORDER BY mr.map_name, winrate DESC
                ''', (guild_id, min_games)) as cursor:
                    rows = await cursor.fetchall()
                    
                    # 맵별로 그룹화해서 반환
                    map_meta = {}
                    for row in rows:
                        map_name = row[0]
                        if map_name not in map_meta:
                            map_meta[map_name] = {
                                'map_name': row[0],
                                'map_type': row[1],
                                'positions': []
                            }
                        
                        map_meta[map_name]['positions'].append({
                            'position': row[2],
                            'games': row[3],
                            'wins': row[4],
                            'winrate': row[5]
                        })
                    
                    return list(map_meta.values())
                    
        except Exception as e:
            print(f"서버 맵 메타 조회 실패: {e}")
            return []

    async def get_server_map_overview(self, guild_id: str) -> Dict:
        """서버 맵 통계 전체 개요"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 전체 통계
                async with db.execute('''
                    SELECT 
                        COUNT(*) as total_matches,
                        COUNT(DISTINCT map_name) as unique_maps,
                        COUNT(DISTINCT map_type) as unique_map_types
                    FROM match_results
                    WHERE guild_id = ? AND map_name IS NOT NULL
                ''', (guild_id,)) as cursor:
                    overview = await cursor.fetchone()
                
                # 맵 타입별 분포
                async with db.execute('''
                    SELECT 
                        map_type,
                        COUNT(*) as count,
                        ROUND(COUNT(*) * 100.0 / (
                            SELECT COUNT(*) FROM match_results 
                            WHERE guild_id = ? AND map_name IS NOT NULL
                        ), 1) as percentage
                    FROM match_results
                    WHERE guild_id = ? AND map_name IS NOT NULL
                    GROUP BY map_type
                    ORDER BY count DESC
                ''', (guild_id, guild_id)) as cursor:
                    type_distribution = await cursor.fetchall()
                
                if not overview or overview[0] == 0:
                    return {}
                
                return {
                    'total_matches': overview[0],
                    'unique_maps': overview[1],
                    'unique_map_types': overview[2],
                    'type_distribution': [
                        {
                            'map_type': row[0],
                            'count': row[1],
                            'percentage': row[2]
                        }
                        for row in type_distribution
                    ]
                }
                    
        except Exception as e:
            print(f"서버 맵 개요 조회 실패: {e}")
            return {}

    def _get_balance_rating(self, balance_score: float) -> str:
        """밸런스 점수를 등급으로 변환"""
        if balance_score <= 5.0:
            return "완벽"
        elif balance_score <= 10.0:
            return "좋음"
        elif balance_score <= 20.0:
            return "보통"
        else:
            return "불균형"

    async def get_user_detailed_map_stats(self, user_id: str, guild_id: str, map_type: str = None) -> List[Dict]:
        """사용자의 상세 맵별 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                base_query = '''
                    SELECT 
                        mr.map_name,
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate,
                        MAX(mr.match_date) as last_played
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_name IS NOT NULL
                '''
                
                params = [user_id, guild_id]
                
                if map_type and map_type != "all":
                    base_query += " AND mr.map_type = ?"
                    params.append(map_type)
                
                base_query += '''
                    GROUP BY mr.map_name, mr.map_type
                    ORDER BY games DESC, winrate DESC
                '''
                
                async with db.execute(base_query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'map_name': row[0],
                            'map_type': row[1],
                            'games': row[2],
                            'wins': row[3],
                            'winrate': row[4],
                            'last_played': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"상세 맵별 통계 조회 실패: {e}")
            return []

    async def get_user_position_map_matrix(self, user_id: str, guild_id: str) -> List[Dict]:
        """사용자의 포지션-맵 매트릭스 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mp.position,
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL 
                        AND mp.position IS NOT NULL
                    GROUP BY mp.position, mr.map_type
                    ORDER BY mp.position, mr.map_type
                ''', (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'position': row[0],
                            'map_type': row[1],
                            'games': row[2],
                            'wins': row[3],
                            'winrate': row[4]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"포지션-맵 매트릭스 조회 실패: {e}")
            return []

    async def get_map_improvement_suggestions(self, user_id: str, guild_id: str) -> Dict:
        """맵/포지션 개선 제안 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 가장 약한 맵 타입 찾기
                async with db.execute('''
                    SELECT 
                        mr.map_type,
                        COUNT(*) as games,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL
                    GROUP BY mr.map_type
                    HAVING COUNT(*) >= 3
                    ORDER BY winrate ASC
                    LIMIT 1
                ''', (user_id, guild_id)) as cursor:
                    weak_type_row = await cursor.fetchone()
                
                # 가장 약한 개별 맵 찾기
                async with db.execute('''
                    SELECT 
                        mr.map_name,
                        mr.map_type,
                        COUNT(*) as games,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_name IS NOT NULL
                    GROUP BY mr.map_name, mr.map_type
                    HAVING COUNT(*) >= 2
                    ORDER BY winrate ASC
                    LIMIT 1
                ''', (user_id, guild_id)) as cursor:
                    weak_map_row = await cursor.fetchone()
                
                # 개선이 필요한 포지션-맵 조합 찾기
                async with db.execute('''
                    SELECT 
                        mp.position,
                        mr.map_type,
                        COUNT(*) as games,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL 
                        AND mp.position IS NOT NULL
                    GROUP BY mp.position, mr.map_type
                    HAVING COUNT(*) >= 2
                    ORDER BY winrate ASC
                    LIMIT 1
                ''', (user_id, guild_id)) as cursor:
                    weak_combo_row = await cursor.fetchone()
                
                result = {}
                
                if weak_type_row:
                    result['weak_type'] = {
                        'map_type': weak_type_row[0],
                        'games': weak_type_row[1],
                        'winrate': weak_type_row[2]
                    }
                
                if weak_map_row:
                    result['weak_map'] = {
                        'map_name': weak_map_row[0],
                        'map_type': weak_map_row[1], 
                        'games': weak_map_row[2],
                        'winrate': weak_map_row[3]
                    }
                
                if weak_combo_row:
                    result['weak_combo'] = {
                        'position': weak_combo_row[0],
                        'map_type': weak_combo_row[1],
                        'games': weak_combo_row[2],
                        'winrate': weak_combo_row[3]
                    }
                
                return result
                    
        except Exception as e:
            print(f"개선 제안 조회 실패: {e}")
            return {}

    async def get_map_teammates_recommendations(self, user_id: str, guild_id: str, map_type: str = None) -> List[Dict]:
        """특정 맵에서 잘하는 추천 팀원들 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                base_query = '''
                    SELECT 
                        mp.user_id,
                        mp.username,
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(mp.won) as wins,
                        ROUND(SUM(mp.won) * 100.0 / COUNT(*), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id != ? AND mr.guild_id = ? 
                        AND mr.map_type IS NOT NULL
                '''
                
                params = [user_id, guild_id]
                
                if map_type and map_type != "all":
                    base_query += " AND mr.map_type = ?"
                    params.append(map_type)
                
                base_query += '''
                    GROUP BY mp.user_id, mp.username, mr.map_type
                    HAVING COUNT(*) >= 3
                    ORDER BY winrate DESC, games DESC
                    LIMIT 10
                '''
                
                async with db.execute(base_query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'map_type': row[2],
                            'games': row[3],
                            'wins': row[4],
                            'winrate': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"추천 팀원 조회 실패: {e}")
            return []

    async def get_teammate_pair_stats(self, user_id: str, guild_id: str, 
                                    my_position: str, teammate_position: str) -> List[TeammatePairStats]:
        """특정 포지션 페어의 승률 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # 같은 팀에서 함께 플레이한 경기들 조회
                query = '''
                    SELECT 
                        teammate.user_id as teammate_id,
                        teammate.username as teammate_name,
                        COUNT(DISTINCT me.match_id) as total_games,
                        SUM(CASE WHEN me.won = 1 THEN 1 ELSE 0 END) as wins
                    FROM match_participants me
                    JOIN match_participants teammate ON (
                        me.match_id = teammate.match_id 
                        AND me.team = teammate.team 
                        AND me.user_id != teammate.user_id
                    )
                    JOIN match_results mr ON me.match_id = mr.id
                    WHERE me.user_id = ? 
                        AND mr.guild_id = ?
                        AND me.position = ? 
                        AND teammate.position = ?
                    GROUP BY teammate.user_id, teammate.username
                    HAVING COUNT(*) >= 1
                    ORDER BY wins DESC, total_games DESC
                '''
                
                async with db.execute(query, (user_id, guild_id, my_position, teammate_position)) as cursor:
                    rows = await cursor.fetchall()
                    
                    pair_stats = []
                    for row in rows:
                        teammate_id, teammate_name, total_games, wins = row
                        winrate = round((wins / total_games) * 100, 1) if total_games > 0 else 0.0
                        
                        stats = TeammatePairStats(
                            teammate_id=teammate_id,
                            teammate_name=teammate_name,
                            my_position=my_position,
                            teammate_position=teammate_position,
                            total_games=total_games,
                            wins=wins,
                            winrate=winrate
                        )
                        pair_stats.append(stats)
                    
                    return pair_stats
                    
        except Exception as e:
            print(f"팀메이트 페어 통계 조회 실패: {e}")
            return []

    async def get_user_team_winrate_analysis(self, user_id: str, guild_id: str) -> Optional[TeamWinrateAnalysis]:
        """사용자의 전체 팀 승률 분석 - 동료 승률 시스템"""
        try:
            # 각 포지션별 동료 승률 조회 (내 포지션 무관)
            tank_teammates = await self.get_teammate_stats_by_position(user_id, guild_id, '탱커')
            dps_teammates = await self.get_teammate_stats_by_position(user_id, guild_id, '딜러')
            support_teammates = await self.get_teammate_stats_by_position(user_id, guild_id, '힐러')
            
            # 사용자 정보 조회
            user_info = await self.get_registered_user_info(guild_id, user_id)
            username = user_info.get('username', 'Unknown') if user_info else 'Unknown'
            
            # 베스트 동료 선정
            best_pairs = self._select_best_teammates(tank_teammates, support_teammates, dps_teammates)

            # 실제 고유 경기 수 조회
            actual_team_games = await self.get_user_actual_team_games(user_id, guild_id)

            return TeamWinrateAnalysis(
                user_id=user_id,
                username=username,
                tank_pairs=tank_teammates,      # 이제 "탱커 동료" 의미
                support_pairs=support_teammates, # 이제 "힐러 동료" 의미  
                dps_pairs=dps_teammates,        # 이제 "딜러 동료" 의미
                best_pairs=best_pairs,
                actual_team_games=actual_team_games
            )
            
        except Exception as e:
            print(f"팀 승률 분석 실패: {e}")
            return None

    async def get_best_pairs_summary(self, user_id: str, guild_id: str) -> Optional[BestPairSummary]:
        """베스트 페어 요약만 조회 (내정보 명령어용)"""
        try:
            analysis = await self.get_user_team_winrate_analysis(user_id, guild_id)
            return analysis.best_pairs if analysis else None
        except Exception as e:
            print(f"베스트 페어 요약 조회 실패: {e}")
            return None

    def _merge_pair_stats(self, pair_list: List[TeammatePairStats]) -> List[TeammatePairStats]:
        """같은 팀메이트의 통계를 병합 (딜러+힐러로 탱커와 함께한 경우)"""
        merged = {}
        
        for pair in pair_list:
            key = pair.teammate_id
            
            if key in merged:
                # 기존 통계와 병합
                existing = merged[key]
                existing.total_games += pair.total_games
                existing.wins += pair.wins
                # 승률 재계산
                existing.winrate = round((existing.wins / existing.total_games) * 100, 1) if existing.total_games > 0 else 0.0
            else:
                merged[key] = pair
        
        # 승률순으로 정렬
        return sorted(merged.values(), key=lambda x: (-x.winrate, -x.total_games))

    def _select_best_pairs(self, tank_pairs: List[TeammatePairStats], 
                        support_pairs: List[TeammatePairStats], 
                        dps_pairs: List[TeammatePairStats]) -> BestPairSummary:
        """베스트 페어 선정 (최소 3경기 이상)"""
        
        def get_best_pair(pairs: List[TeammatePairStats]) -> Optional[TeammatePairStats]:
            # 3경기 이상 + 승률 높은 순으로 선정
            qualified = [p for p in pairs if p.total_games >= 3]
            return qualified[0] if qualified else None
        
        return BestPairSummary(
            tank_pair=get_best_pair(tank_pairs),
            support_pair=get_best_pair(support_pairs),
            dps_pair=get_best_pair(dps_pairs)
        )

    def get_position_display_name(self, position: str) -> str:
        """포지션 표시명 변환"""
        position_map = {
            '탱': '탱커',
            '딜': '딜러', 
            '힐': '힐러'
        }
        return position_map.get(position, position)

    def format_pair_winrate(self, pair: TeammatePairStats, show_emoji: bool = True) -> str:
        """페어 승률 포맷팅"""
        emoji = ""
        if show_emoji:
            if pair.winrate >= 70:
                emoji = " 🔥"
            elif pair.winrate <= 40:
                emoji = " ⚠️"
        
        return f"{pair.teammate_name}: {pair.winrate}% ({pair.wins}승 {pair.total_games - pair.wins}패){emoji}"

    async def debug_team_winrate_data(self, user_id: str, guild_id: str) -> Dict:
        """팀 승률 데이터 디버깅용"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # 사용자의 모든 경기 데이터 조회
                async with db.execute('''
                    SELECT mp.match_id, mp.position, mp.won, mp.team,
                        GROUP_CONCAT(teammate.username || ':' || teammate.position) as teammates
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    LEFT JOIN match_participants teammate ON (
                        mp.match_id = teammate.match_id 
                        AND mp.team = teammate.team 
                        AND mp.user_id != teammate.user_id
                    )
                    WHERE mp.user_id = ? AND mr.guild_id = ?
                    GROUP BY mp.match_id, mp.position, mp.won, mp.team
                ''', (user_id, guild_id)) as cursor:
                    matches = await cursor.fetchall()
                    
                    debug_info = {
                        'total_matches': len(matches),
                        'matches': [],
                        'positions_played': set(),
                        'teammates_by_position': {}
                    }
                    
                    for match in matches:
                        match_id, position, won, team, teammates_str = match
                        teammates = teammates_str.split(',') if teammates_str else []
                        
                        debug_info['matches'].append({
                            'match_id': match_id,
                            'my_position': position,
                            'won': bool(won),
                            'team': team,
                            'teammates': teammates
                        })
                        
                        if position:
                            debug_info['positions_played'].add(position)
                    
                    debug_info['positions_played'] = list(debug_info['positions_played'])
                    
                    return debug_info
                    
        except Exception as e:
            print(f"팀 승률 디버깅 실패: {e}")
            return {'error': str(e)}

    async def get_user_map_type_stats(self, user_id: str, guild_id: str):
        """사용자의 맵 타입별 통계 (database.py에 추가)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                query = '''
                    SELECT 
                        mr.map_type,
                        COUNT(*) as games,
                        SUM(CASE WHEN mp.won = 1 THEN 1 ELSE 0 END) as wins,
                        ROUND(AVG(CASE WHEN mp.won = 1 THEN 100.0 ELSE 0.0 END), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? AND mr.map_type IS NOT NULL
                    GROUP BY mr.map_type
                    HAVING COUNT(*) >= 3
                    ORDER BY winrate DESC, games DESC
                '''
                
                async with db.execute(query, (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'map_type': row[0],
                            'games': row[1],
                            'wins': row[2],
                            'winrate': row[3]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"맵 타입별 통계 조회 실패: {e}")
            return []

    async def get_user_best_worst_maps(self, user_id: str, guild_id: str, limit: int = 3):
        """사용자의 베스트/워스트 맵 (database.py에 추가)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                query = '''
                    SELECT 
                        mr.map_name,
                        COUNT(*) as games,
                        SUM(CASE WHEN mp.won = 1 THEN 1 ELSE 0 END) as wins,
                        ROUND(AVG(CASE WHEN mp.won = 1 THEN 100.0 ELSE 0.0 END), 1) as winrate
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ? AND mr.map_name IS NOT NULL
                    GROUP BY mr.map_name
                    HAVING COUNT(*) >= 3
                    ORDER BY winrate DESC, games DESC
                '''
                
                async with db.execute(query, (user_id, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    maps_data = [
                        {
                            'map_name': row[0],
                            'games': row[1],
                            'wins': row[2],
                            'winrate': row[3]
                        }
                        for row in rows
                    ]
                    
                    return {
                        'best': maps_data[:limit] if maps_data else [],
                        'worst': maps_data[-limit:] if len(maps_data) > limit else []
                    }
                    
        except Exception as e:
            print(f"베스트/워스트 맵 조회 실패: {e}")
            return {'best': [], 'worst': []}

    async def get_user_recent_matches(self, user_id: str, guild_id: str, limit: int = 5):
        """사용자의 최근 경기"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                query = '''
                    SELECT 
                        mp.won,
                        mp.position,
                        mr.match_date
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ?
                    ORDER BY mr.match_date DESC
                    LIMIT ?
                '''
                
                async with db.execute(query, (user_id, guild_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'won': bool(row[0]),
                            'position': row[1],
                            'match_date': row[2]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"최근 경기 조회 실패: {e}")
            return []

    async def get_user_actual_team_games(self, user_id: str, guild_id: str) -> int:
        """사용자의 실제 고유 경기 수 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT COUNT(DISTINCT mr.id)
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ?
                ''', (user_id, guild_id)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else 0
                    
        except Exception as e:
            print(f"실제 팀 경기 수 조회 실패: {e}")
            return 0

    async def get_teammate_stats_by_position(self, user_id: str, guild_id: str, teammate_position: str) -> List[TeammatePairStats]:
        """특정 포지션 동료들과의 승률 통계 조회 (내 포지션 무관)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                query = '''
                    SELECT 
                        teammate.user_id as teammate_id,
                        teammate.username as teammate_name,
                        COUNT(*) as total_games,
                        SUM(me.won) as wins
                    FROM match_participants me
                    JOIN match_participants teammate ON (
                        me.match_id = teammate.match_id 
                        AND me.team = teammate.team 
                        AND me.user_id != teammate.user_id
                    )
                    JOIN match_results mr ON me.match_id = mr.id
                    WHERE me.user_id = ? 
                        AND mr.guild_id = ?
                        AND teammate.position = ?  -- 동료의 포지션만 지정
                    GROUP BY teammate.user_id, teammate.username
                    HAVING COUNT(*) >= 1
                    ORDER BY (SUM(me.won) * 100.0 / COUNT(*)) DESC, COUNT(*) DESC
                '''
                
                async with db.execute(query, (user_id, guild_id, teammate_position)) as cursor:
                    rows = await cursor.fetchall()
                    
                    teammate_stats = []
                    for row in rows:
                        teammate_id, teammate_name, total_games, wins = row
                        winrate = round((wins / total_games) * 100, 1) if total_games > 0 else 0.0
                        
                        stats = TeammatePairStats(
                            teammate_id=teammate_id,
                            teammate_name=teammate_name,
                            my_position="모든포지션",  # 내 포지션은 무관
                            teammate_position=teammate_position,
                            total_games=total_games,
                            wins=wins,
                            winrate=winrate
                        )
                        teammate_stats.append(stats)
                    
                    return teammate_stats
                    
        except Exception as e:
            print(f"동료 포지션별 승률 조회 실패 ({teammate_position}): {e}")
            return []

    def _select_best_teammates(self, tank_teammates: List[TeammatePairStats], 
                            support_teammates: List[TeammatePairStats], 
                            dps_teammates: List[TeammatePairStats]) -> BestPairSummary:
        """베스트 동료 선정 (최소 3경기 이상)"""
        
        def get_best_teammate(teammates: List[TeammatePairStats]) -> Optional[TeammatePairStats]:
            # 3경기 이상 + 승률 높은 순으로 선정
            qualified = [t for t in teammates if t.total_games >= 3]
            return qualified[0] if qualified else None
        
        return BestPairSummary(
            tank_pair=get_best_teammate(tank_teammates),    # 베스트 탱커 동료
            support_pair=get_best_teammate(support_teammates), # 베스트 힐러 동료
            dps_pair=get_best_teammate(dps_teammates)       # 베스트 딜러 동료
        )
    
    async def initialize_wordle_tables(self):
        """띵지워들 관련 테이블 초기화"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # 1. 기존 users 테이블에 워들 관련 컬럼 추가
                await self._add_wordle_columns_to_users(db)
                
                # 2. 워들 게임 테이블
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS wordle_games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id TEXT NOT NULL,
                        word TEXT NOT NULL,
                        hint TEXT,
                        creator_id TEXT NOT NULL,
                        creator_username TEXT NOT NULL,
                        bet_points INTEGER NOT NULL DEFAULT 0,
                        total_pool INTEGER NOT NULL DEFAULT 0,
                        is_active BOOLEAN DEFAULT TRUE,
                        is_completed BOOLEAN DEFAULT FALSE,
                        winner_id TEXT,
                        winner_username TEXT,
                        creator_reward_paid BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL,
                        completed_at TIMESTAMP
                    )
                ''')
                
                # 3. 워들 도전 기록 테이블
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS wordle_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        bet_amount INTEGER NOT NULL,
                        remaining_points INTEGER NOT NULL,
                        points_per_failure INTEGER NOT NULL,
                        attempts_used INTEGER DEFAULT 0,
                        is_completed BOOLEAN DEFAULT FALSE,
                        is_winner BOOLEAN DEFAULT FALSE,
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        FOREIGN KEY (game_id) REFERENCES wordle_games(id)
                    )
                ''')
                
                # 4. 워들 추측 로그 테이블
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS wordle_guesses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        attempt_id INTEGER NOT NULL,
                        guess_word TEXT NOT NULL,
                        result_pattern TEXT NOT NULL,
                        guess_number INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (attempt_id) REFERENCES wordle_attempts(id)
                    )
                ''')
                
                # 5. 워들 난이도 평가 테이블
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS wordle_ratings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id INTEGER NOT NULL,
                        user_id TEXT NOT NULL,
                        username TEXT NOT NULL,
                        rating TEXT NOT NULL CHECK (rating IN ('쉬움', '적절함', '어려움')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (game_id) REFERENCES wordle_games(id),
                        UNIQUE(game_id, user_id)
                    )
                ''')
                
                # 6. 인덱스 생성 (성능 최적화)
                await self._create_wordle_indexes(db)
                
                await db.commit()
                print("✅ 띵지워들 테이블이 성공적으로 생성되었습니다.")
                
            except Exception as e:
                await db.rollback()
                print(f"❌ 띵지워들 테이블 생성 중 오류: {e}")
                raise

    async def _add_wordle_columns_to_users(self, db):
        """기존 users 테이블에 워들 관련 컬럼 추가"""
        try:
            # wordle_points 컬럼 추가
            await db.execute('ALTER TABLE registered_users ADD COLUMN wordle_points INTEGER DEFAULT 10000')
            print("✅ users 테이블에 wordle_points 컬럼 추가")
        except Exception:
            # 이미 컬럼이 존재하는 경우 무시
            pass
        
        try:
            # daily_points_claimed 컬럼 추가
            await db.execute('ALTER TABLE registered_users ADD COLUMN daily_points_claimed TEXT')
            print("✅ users 테이블에 daily_points_claimed 컬럼 추가")
        except Exception:
            # 이미 컬럼이 존재하는 경우 무시
            pass

    async def _create_wordle_indexes(self, db):
        """워들 관련 테이블 인덱스 생성"""
        indexes = [
            # 게임 검색 최적화
            'CREATE INDEX IF NOT EXISTS idx_wordle_games_active ON wordle_games(is_active, expires_at)',
            'CREATE INDEX IF NOT EXISTS idx_wordle_games_creator ON wordle_games(creator_id)',
            'CREATE INDEX IF NOT EXISTS idx_wordle_games_guild ON wordle_games(guild_id)',
            
            # 도전 기록 최적화
            'CREATE INDEX IF NOT EXISTS idx_wordle_attempts_game ON wordle_attempts(game_id)',
            'CREATE INDEX IF NOT EXISTS idx_wordle_attempts_user ON wordle_attempts(user_id)',
            
            # 추측 로그 최적화
            'CREATE INDEX IF NOT EXISTS idx_wordle_guesses_attempt ON wordle_guesses(attempt_id)',
            
            # 평가 최적화
            'CREATE INDEX IF NOT EXISTS idx_wordle_ratings_game ON wordle_ratings(game_id)',
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
        
        print("✅ 띵지워들 인덱스 생성 완료")

    async def get_user_points(self, guild_id: str, user_id: str) -> int:
        """등록된 사용자의 포인트 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT wordle_points FROM registered_users 
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else None  # 미등록시 None 반환
        except Exception as e:
            print(f"포인트 조회 실패: {e}")
            return None
    
    async def update_user_points(self, user_id: str, points: int) -> bool:
        """사용자 포인트 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE users 
                    SET wordle_points = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE discord_id = ?
                ''', (points, user_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"포인트 업데이트 실패: {e}")
            return False
    
    async def add_user_points(self, guild_id: str, user_id: str, points: int) -> bool:
        """등록된 사용자만 포인트 변경 가능"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    UPDATE registered_users 
                    SET wordle_points = wordle_points + ?
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (points, guild_id, user_id))
                
                if cursor.rowcount == 0:
                    return False  # 등록된 사용자가 아님
                    
                await db.commit()
                return True
        except Exception as e:
            print(f"포인트 변경 실패: {e}")
            return False
    
    async def claim_daily_points(self, guild_id: str, user_id: str) -> bool:
        """등록된 사용자만 일일 포인트 수령 가능"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            async with aiosqlite.connect(self.db_path) as db:
                # 등록된 사용자인지 확인 + 오늘 이미 받았는지 확인
                async with db.execute('''
                    SELECT daily_points_claimed FROM registered_users 
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    result = await cursor.fetchone()
                    
                if not result:
                    return False  # 등록된 사용자가 아님
                    
                if result[0] == today:
                    return False  # 이미 오늘 받음
                
                # 일일 포인트 지급
                await db.execute('''
                    UPDATE registered_users 
                    SET wordle_points = wordle_points + 1000,
                        daily_points_claimed = ?
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (today, guild_id, user_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"일일 포인트 지급 실패: {e}")
            return False

    async def create_game(self, game: WordleGame) -> Optional[int]:
        """새 게임 생성"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO wordle_games (
                        guild_id, word, hint, creator_id, creator_username,
                        bet_points, total_pool, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    game.guild_id, game.word, game.hint, game.creator_id,
                    game.creator_username, game.bet_points, game.bet_points,
                    datetime.now(), game.expires_at
                ))
                
                game_id = cursor.lastrowid
                await db.commit()
                return game_id
        except Exception as e:
            print(f"게임 생성 실패: {e}")
            return None
    
    async def get_active_games(self, guild_id: str) -> List[Dict]:
        """활성 게임 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT id, word, hint, creator_id, creator_username, bet_points, total_pool,
                            created_at, expires_at
                    FROM wordle_games
                    WHERE guild_id = ? AND is_active = 1 AND is_completed = 0
                      AND expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at ASC
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'id': row[0],
                            'word': row[1],
                            'hint': row[2],
                            'creator_id': row[3],
                            'creator_username': row[4],
                            'bet_points': row[5],
                            'total_pool': row[6],
                            'created_at': row[7],
                            'expires_at': row[8]
                        }
                        for row in rows
                    ]
        except Exception as e:
            print(f"활성 게임 조회 실패: {e}")
            return []
    
    async def get_game_by_id(self, game_id: int) -> Optional[Dict]:
        """ID로 게임 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM wordle_games WHERE id = ?
                ''', (game_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
        except Exception as e:
            print(f"게임 조회 실패: {e}")
            return None
    
    async def delete_game(self, game_id: int, creator_id: str) -> bool:
        """게임 삭제 (본인만 가능)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    DELETE FROM wordle_games 
                    WHERE id = ? AND creator_id = ? AND is_completed = 0
                ''', (game_id, creator_id))
                
                affected = cursor.rowcount
                await db.commit()
                return affected > 0
        except Exception as e:
            print(f"게임 삭제 실패: {e}")
            return False
    
    async def complete_game(self, game_id: int, winner_id: Optional[str] = None, 
                           winner_username: Optional[str] = None) -> bool:
        """게임 완료 처리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE wordle_games 
                    SET is_completed = 1, is_active = 0,
                        winner_id = ?, winner_username = ?,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (winner_id, winner_username, game_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"게임 완료 처리 실패: {e}")
            return False
    
    async def add_to_pool(self, game_id: int, amount: int) -> bool:
        """게임 포인트 풀에 포인트 추가"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE wordle_games 
                    SET total_pool = total_pool + ?
                    WHERE id = ?
                ''', (amount, game_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"포인트 풀 업데이트 실패: {e}")
            return False
    
    async def create_attempt(self, attempt: WordleAttempt) -> Optional[int]:
        """새 도전 기록 생성"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    INSERT INTO wordle_attempts (
                        game_id, user_id, username, bet_amount, 
                        remaining_points, points_per_failure, started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    attempt.game_id, attempt.user_id, attempt.username,
                    attempt.bet_amount, attempt.remaining_points,
                    attempt.points_per_failure, datetime.now()
                ))
                
                attempt_id = cursor.lastrowid
                await db.commit()
                return attempt_id
        except Exception as e:
            print(f"도전 기록 생성 실패: {e}")
            return None
    
    async def get_user_attempt(self, game_id: int, user_id: str) -> Optional[Dict]:
        """사용자의 특정 게임 도전 기록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM wordle_attempts 
                    WHERE game_id = ? AND user_id = ?
                ''', (game_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
        except Exception as e:
            print(f"도전 기록 조회 실패: {e}")
            return None
    
    async def update_attempt_progress(self, attempt_id: int, remaining_points: int, 
                                    attempts_used: int) -> bool:
        """도전 진행 상황 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE wordle_attempts 
                    SET remaining_points = ?, attempts_used = ?
                    WHERE id = ?
                ''', (remaining_points, attempts_used, attempt_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"도전 진행 상황 업데이트 실패: {e}")
            return False
    
    async def complete_attempt(self, attempt_id: int, is_winner: bool) -> bool:
        """도전 완료 처리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE wordle_attempts 
                    SET is_completed = 1, is_winner = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (is_winner, attempt_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"도전 완료 처리 실패: {e}")
            return False
    
    async def add_guess(self, guess: WordleGuess) -> bool:
        """추측 기록 추가"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO wordle_guesses (
                        attempt_id, guess_word, result_pattern, 
                        guess_number, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    guess.attempt_id, guess.guess_word, guess.result_pattern,
                    guess.guess_number, datetime.now()
                ))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"추측 기록 추가 실패: {e}")
            return False
    
    async def get_attempt_guesses(self, attempt_id: int) -> List[Dict]:
        """특정 도전의 모든 추측 기록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT guess_word, result_pattern, guess_number, created_at
                    FROM wordle_guesses
                    WHERE attempt_id = ?
                    ORDER BY guess_number ASC
                ''', (attempt_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'guess_word': row[0],
                            'result_pattern': row[1],
                            'guess_number': row[2],
                            'created_at': row[3]
                        }
                        for row in rows
                    ]
        except Exception as e:
            print(f"추측 기록 조회 실패: {e}")
            return []
    
    async def add_rating(self, rating: WordleRating) -> bool:
        """난이도 평가 추가"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO wordle_ratings (
                        game_id, user_id, username, rating, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    rating.game_id, rating.user_id, rating.username,
                    rating.rating, datetime.now()
                ))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"난이도 평가 추가 실패: {e}")
            return False
    
    async def get_game_ratings(self, game_id: int) -> Dict[str, int]:
        """게임의 난이도 평가 집계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT rating, COUNT(*) 
                    FROM wordle_ratings 
                    WHERE game_id = ?
                    GROUP BY rating
                ''', (game_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    ratings = {"쉬움": 0, "적절함": 0, "어려움": 0}
                    for rating, count in rows:
                        ratings[rating] = count
                    
                    return ratings
        except Exception as e:
            print(f"난이도 평가 조회 실패: {e}")
            return {"쉬움": 0, "적절함": 0, "어려움": 0}
    
    async def get_expired_games(self) -> List[Dict]:
        """만료된 게임들 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT id, creator_id, bet_points, total_pool
                    FROM wordle_games
                    WHERE is_active = 1 AND is_completed = 0 
                      AND expires_at <= CURRENT_TIMESTAMP
                ''') as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'id': row[0],
                            'creator_id': row[1], 
                            'bet_points': row[2],
                            'total_pool': row[3]
                        }
                        for row in rows
                    ]
        except Exception as e:
            print(f"만료 게임 조회 실패: {e}")
            return []
    
    async def expire_game(self, game_id: int) -> bool:
        """게임 만료 처리"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE wordle_games 
                    SET is_active = 0, completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (game_id,))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"게임 만료 처리 실패: {e}")
            return False
        
    async def calculate_creator_reward(self, game_id: int) -> int:
        """난이도 평가를 바탕으로 출제자 보상 계산"""
        try:
            ratings = await self.get_game_ratings(game_id)
            total_ratings = sum(ratings.values())
            
            if total_ratings == 0:
                return 50  # 기본 참여 보상
            
            # 적절함이 50% 이상이면 200점, 아니면 50점
            appropriate_percentage = (ratings["적절함"] / total_ratings) * 100
            
            if appropriate_percentage >= 50:
                return 200
            else:
                return 50
                
        except Exception as e:
            print(f"출제자 보상 계산 실패: {e}")
            return 50
    
    async def award_creator_points(self, game_id: int) -> bool:
        """출제자에게 보상 지급"""
        try:
            game = await self.get_game_by_id(game_id)
            if not game or not game['is_completed']:
                return False
            
            guild_id = game['guild_id']

            reward = await self.calculate_creator_reward(game_id)
            creator_id = game['creator_id']
            
            # 포인트 지급
            success = await self.add_user_points(guild_id, creator_id, reward)
            
            if success:
                print(f"출제자 보상 지급 완료: {creator_id} -> {reward}점")
            
            return success
            
        except Exception as e:
            print(f"출제자 보상 지급 실패: {e}")
            return False

    async def safe_transfer_points(self, from_user_id: str, to_user_id: str, amount: int) -> bool:
        """안전한 포인트 이전 (트랜잭션)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('BEGIN TRANSACTION')
                
                try:
                    # 송금자 포인트 확인
                    async with db.execute('''
                        SELECT wordle_points FROM users WHERE discord_id = ?
                    ''', (from_user_id,)) as cursor:
                        result = await cursor.fetchone()
                        if not result or result[0] < amount:
                            await db.execute('ROLLBACK')
                            return False
                    
                    # 송금자 포인트 차감
                    await db.execute('''
                        UPDATE users 
                        SET wordle_points = wordle_points - ?, updated_at = CURRENT_TIMESTAMP
                        WHERE discord_id = ?
                    ''', (amount, from_user_id))
                    
                    # 수취자 포인트 추가 (없으면 생성)
                    await db.execute('''
                        INSERT OR IGNORE INTO users (discord_id, username, wordle_points)
                        VALUES (?, 'Unknown', 0)
                    ''', (to_user_id,))
                    
                    await db.execute('''
                        UPDATE users 
                        SET wordle_points = wordle_points + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE discord_id = ?
                    ''', (amount, to_user_id))
                    
                    await db.execute('COMMIT')
                    return True
                    
                except Exception as e:
                    await db.execute('ROLLBACK')
                    print(f"포인트 이전 트랜잭션 실패: {e}")
                    return False
                    
        except Exception as e:
            print(f"포인트 이전 실패: {e}")
            return False
    
    async def safe_reward_winner(self, game_id: int, winner_id: str, total_pool: int) -> bool:
        """안전한 승자 보상 지급"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('BEGIN TRANSACTION')
                
                try:
                    # 게임 상태 확인
                    async with db.execute('''
                        SELECT is_completed, total_pool FROM wordle_games WHERE id = ?
                    ''', (game_id,)) as cursor:
                        result = await cursor.fetchone()
                        if not result or result[0]:  # 이미 완료된 게임
                            await db.execute('ROLLBACK')
                            return False
                    
                    # 승자에게 포인트 지급
                    await db.execute('''
                        INSERT OR IGNORE INTO users (discord_id, username, wordle_points)
                        VALUES (?, 'Winner', 0)
                    ''', (winner_id,))
                    
                    await db.execute('''
                        UPDATE users 
                        SET wordle_points = wordle_points + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE discord_id = ?
                    ''', (total_pool, winner_id))
                    
                    await db.execute('COMMIT')
                    return True
                    
                except Exception as e:
                    await db.execute('ROLLBACK')
                    print(f"승자 보상 트랜잭션 실패: {e}")
                    return False
                    
        except Exception as e:
            print(f"승자 보상 실패: {e}")
            return False
    
    async def get_top_players(self, limit: int = 10) -> List[Dict]:
        """포인트 상위 플레이어 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT user_id, username, wordle_points
                    FROM registered_users
                    WHERE wordle_points > 0 AND is_active = TRUE
                    ORDER BY wordle_points DESC
                    LIMIT ?
                ''', (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'points': row[2],
                            'rank': i + 1
                        }
                        for i, row in enumerate(rows)
                    ]
        except Exception as e:
            print(f"상위 플레이어 조회 실패: {e}")
            return []
    
    async def get_user_stats(self, guild_id: str, user_id: str) -> Dict:
        """사용자 게임 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 기본 포인트 조회
                points = await self.get_user_points(guild_id, user_id)
                
                # 게임 통계 조회
                async with db.execute('''
                    SELECT 
                        COUNT(*) as games_created,
                        COUNT(CASE WHEN is_completed = 1 AND winner_id IS NOT NULL THEN 1 END) as games_solved
                    FROM wordle_games 
                    WHERE creator_id = ?
                ''', (user_id,)) as cursor:
                    creator_stats = await cursor.fetchone()
                
                async with db.execute('''
                    SELECT 
                        COUNT(*) as games_attempted,
                        COUNT(CASE WHEN is_winner = 1 THEN 1 END) as games_won,
                        AVG(attempts_used) as avg_attempts
                    FROM wordle_attempts
                    WHERE user_id = ? AND is_completed = 1
                ''', (user_id,)) as cursor:
                    player_stats = await cursor.fetchone()
                
                return {
                    'points': points,
                    'games_created': creator_stats[0] if creator_stats else 0,
                    'games_solved': creator_stats[1] if creator_stats else 0,
                    'games_attempted': player_stats[0] if player_stats else 0,
                    'games_won': player_stats[1] if player_stats else 0,
                    'avg_attempts': round(player_stats[2], 1) if player_stats and player_stats[2] else 0,
                    'win_rate': round((player_stats[1] / player_stats[0]) * 100, 1) if player_stats and player_stats[0] > 0 else 0
                }
                
        except Exception as e:
            print(f"사용자 통계 조회 실패: {e}")
            return {'points': 0, 'games_created': 0, 'games_solved': 0, 'games_attempted': 0, 'games_won': 0, 'avg_attempts': 0, 'win_rate': 0}

    async def create_inter_guild_scrim_tables(self):
        """길드 간 스크림 관련 테이블 생성 (내전과 별도)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 길드 간 스크림 모집 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inter_guild_scrims (
                    id TEXT PRIMARY KEY,
                    guild_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    description TEXT,
                    tier_range TEXT NOT NULL,
                    opponent_team TEXT,
                    scrim_date TEXT NOT NULL,
                    deadline_date TEXT NOT NULL,
                    channel_id TEXT,
                    max_participants INTEGER DEFAULT 5,
                    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'closed', 'cancelled')),
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 길드 간 스크림 참가자 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inter_guild_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrim_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('joined', 'declined', 'late_join')),
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scrim_id) REFERENCES inter_guild_scrims(id),
                    UNIQUE(scrim_id, user_id)
                )
            ''')
            
            # 길드 간 스크림 경기 결과 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inter_guild_matches (
                    id TEXT PRIMARY KEY,
                    scrim_id TEXT NOT NULL,
                    match_number INTEGER NOT NULL DEFAULT 1,
                    our_team_score INTEGER DEFAULT 0,
                    opponent_team_score INTEGER DEFAULT 0,
                    winning_team TEXT NOT NULL CHECK (winning_team IN ('our_team', 'opponent_team')),
                    map_name TEXT,
                    match_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    FOREIGN KEY (scrim_id) REFERENCES inter_guild_scrims(id)
                )
            ''')
            
            # 길드 간 스크림 경기 참가자 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inter_guild_match_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    position TEXT NOT NULL CHECK (position IN ('탱커', '딜러', '힐러')),
                    won BOOLEAN NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (match_id) REFERENCES inter_guild_matches(id)
                )
            ''')

            # 스크림 시간 조합 테이블 (복수 날짜/시간 지원)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_time_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrim_id TEXT NOT NULL,
                    date_str TEXT NOT NULL,
                    time_slot TEXT NOT NULL,
                    date_display TEXT NOT NULL,
                    is_custom_time BOOLEAN DEFAULT FALSE,
                    finalized BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scrim_id) REFERENCES inter_guild_scrims(id),
                    UNIQUE(scrim_id, date_str, time_slot)
                )
            ''')
            
            # 포지션별 참가자 테이블 (기존 inter_guild_participants 확장)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS scrim_position_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrim_id TEXT NOT NULL,
                    time_slot_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    position TEXT NOT NULL CHECK (position IN ('탱커', '딜러', '힐러', '플렉스')),
                    status TEXT DEFAULT 'joined' CHECK (status IN ('joined', 'declined')),
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (scrim_id) REFERENCES inter_guild_scrims(id),
                    FOREIGN KEY (time_slot_id) REFERENCES scrim_time_slots(id),
                    UNIQUE(time_slot_id, user_id, position)
                )
            ''')
            
            # 글로벌 클랜 공유 테이블 (기존 clan_teams와 별도)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS global_shared_clans (
                    clan_name TEXT PRIMARY KEY,
                    origin_guild_id TEXT NOT NULL,
                    origin_guild_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 1,
                    verified BOOLEAN DEFAULT FALSE
                )
            ''')
            
            # 서버별 클랜 매핑 테이블
            await db.execute('''
                CREATE TABLE IF NOT EXISTS guild_clan_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id TEXT NOT NULL,
                    clan_name TEXT NOT NULL,
                    is_primary BOOLEAN DEFAULT FALSE,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (clan_name) REFERENCES global_shared_clans(clan_name),
                    UNIQUE(guild_id, clan_name)
                )
            ''')
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_inter_guild_scrims_guild_status ON inter_guild_scrims(guild_id, status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_inter_guild_scrims_deadline ON inter_guild_scrims(deadline_date, status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_inter_guild_participants_scrim ON inter_guild_participants(scrim_id, status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_inter_guild_matches_scrim ON inter_guild_matches(scrim_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_scrim_time_slots_scrim ON scrim_time_slots(scrim_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_position_participants_time_slot ON scrim_position_participants(time_slot_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_position_participants_user ON scrim_position_participants(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_global_clans_usage ON global_shared_clans(usage_count DESC)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_guild_clan_mapping_guild ON guild_clan_mapping(guild_id)')

            await db.commit()
            print("🎯 길드 간 스크림 테이블이 생성되었습니다.")
            
    async def create_scrim(self, scrim_data: Dict[str, Any]) -> str:
        """새 길드 간 스크림 모집 생성"""
        async with aiosqlite.connect(self.db_path) as db:
            scrim_id = self.generate_uuid()
            created_at = datetime.now(timezone.utc).isoformat()
            
            await db.execute('''
                INSERT INTO inter_guild_scrims 
                (id, guild_id, title, content, tier_range, opponent_team, 
                 scrim_date, deadline_date, channel_id, max_participants, 
                 status, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                scrim_id, scrim_data['guild_id'], scrim_data['title'],
                scrim_data['content'], scrim_data['tier_range'], scrim_data['opponent_team'],
                scrim_data['scrim_date'], scrim_data['deadline_date'], scrim_data['channel_id'],
                5, 'active', scrim_data['created_by'], created_at
            ))
            
            await db.commit()
            return scrim_id

    async def get_scrim_by_id(self, scrim_id: str) -> Optional[Dict[str, Any]]:
        """ID로 길드 간 스크림 모집 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT * FROM inter_guild_scrims WHERE id = ?
            ''', (scrim_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def get_active_scrims(self, guild_id: str) -> List[Dict[str, Any]]:
        """활성 길드 간 스크림 모집 목록 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT s.*, 
                       COUNT(p.id) as participant_count
                FROM inter_guild_scrims s
                LEFT JOIN inter_guild_participants p ON s.id = p.scrim_id 
                    AND p.status = 'joined'
                WHERE s.guild_id = ? AND s.status = 'active'
                GROUP BY s.id
                ORDER BY s.scrim_date ASC
            ''', (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def add_participant(self, scrim_id: str, user_id: str, 
                            username: str, status: str = 'joined') -> bool:
        """길드 간 스크림 참가자 추가/업데이트"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now(timezone.utc).isoformat()
            
            await db.execute('''
                INSERT OR REPLACE INTO inter_guild_participants 
                (scrim_id, user_id, username, status, joined_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (scrim_id, user_id, username, status, now, now))
            
            await db.commit()
            return True

    async def get_participants(self, scrim_id: str) -> List[Dict[str, Any]]:
        """길드 간 스크림 모집 참가자 목록 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT * FROM inter_guild_participants 
                WHERE scrim_id = ?
                ORDER BY joined_at ASC
            ''', (scrim_id,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def update_scrim_status(self, scrim_id: str, status: str) -> bool:
        """길드 간 스크림 모집 상태 업데이트"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE inter_guild_scrims 
                SET status = ? 
                WHERE id = ?
            ''', (status, scrim_id))
            
            await db.commit()
            return True

    async def get_expired_scrims(self) -> List[Dict[str, Any]]:
        """마감 시간이 지난 길드 간 스크림 모집 조회"""
        current_time = datetime.now(timezone.utc).isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT * FROM inter_guild_scrims 
                WHERE status = 'active' 
                AND deadline_date < ?
            ''', (current_time,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_scrim_statistics(self, guild_id: str) -> Dict[str, Any]:
        """길드 간 스크림 모집 통계 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            # 전체 통계
            async with db.execute('''
                SELECT 
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as completed_count,
                    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_count,
                    COUNT(*) as total_count
                FROM inter_guild_scrims
                WHERE guild_id = ?
            ''', (guild_id,)) as cursor:
                stats_row = await cursor.fetchone()
            
            # 참가자 통계
            async with db.execute('''
                SELECT AVG(participant_count) as avg_participants
                FROM (
                    SELECT COUNT(p.id) as participant_count
                    FROM inter_guild_scrims s
                    LEFT JOIN inter_guild_participants p ON s.id = p.scrim_id 
                        AND p.status = 'joined'
                    WHERE s.guild_id = ? AND s.status IN ('closed', 'cancelled')
                    GROUP BY s.id
                )
            ''', (guild_id,)) as cursor:
                avg_row = await cursor.fetchone()
            
            return {
                'active': stats_row[0] if stats_row else 0,
                'completed': stats_row[1] if stats_row else 0,
                'cancelled': stats_row[2] if stats_row else 0,
                'total': stats_row[3] if stats_row else 0,
                'avg_participants': round(avg_row[0], 1) if avg_row and avg_row[0] else 0
            }

    async def delete_scrim(self, scrim_id: str) -> bool:
        """길드 간 스크림 모집 삭제 (관련 데이터도 함께 삭제)"""
        async with aiosqlite.connect(self.db_path) as db:
            # 참가자 데이터 먼저 삭제
            await db.execute('DELETE FROM inter_guild_participants WHERE scrim_id = ?', (scrim_id,))
            
            # 스크림 모집 삭제
            await db.execute('DELETE FROM inter_guild_scrims WHERE id = ?', (scrim_id,))
            
            await db.commit()
            return True

    async def get_user_participation_history(self, guild_id: str, user_id: str) -> List[Dict]:
        """특정 사용자의 길드 간 스크림 참가 이력"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT s.title, s.scrim_date, s.status as scrim_status,
                        p.status as participation_status, p.joined_at
                    FROM inter_guild_scrims s
                    JOIN inter_guild_participants p ON s.id = p.scrim_id
                    WHERE s.guild_id = ? AND p.user_id = ?
                    ORDER BY s.scrim_date DESC
                    LIMIT 20
                ''', (guild_id, user_id)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    
                    return [dict(zip(columns, row)) for row in results]
                    
        except Exception as e:
            print(f"❌ 사용자 참가 이력 조회 실패: {e}")
            return []

    async def cleanup_old_scrims(self, days_old: int = 30) -> int:
        """오래된 길드 간 스크림 데이터 정리"""
        try:
            from datetime import timedelta
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            async with aiosqlite.connect(self.db_path) as db:
                # 오래된 참가자 데이터 삭제
                await db.execute('''
                    DELETE FROM inter_guild_participants 
                    WHERE scrim_id IN (
                        SELECT id FROM inter_guild_scrims 
                        WHERE created_at < ? AND status IN ('closed', 'cancelled')
                    )
                ''', (cutoff_date,))
                
                # 오래된 스크림 모집 삭제
                cursor = await db.execute('''
                    DELETE FROM inter_guild_scrims 
                    WHERE created_at < ? AND status IN ('closed', 'cancelled')
                ''', (cutoff_date,))
                
                deleted_count = cursor.rowcount
                await db.commit()
                
                return deleted_count
                
        except Exception as e:
            print(f"❌ 오래된 데이터 정리 실패: {e}")
            return 0

    async def get_available_clans_for_dropdown(self, guild_id: str) -> List[Dict[str, str]]:
        """드롭다운용 클랜 목록 조회 (등록된 클랜 + 글로벌 클랜)"""
        async with aiosqlite.connect(self.db_path) as db:
            # 1. 현재 서버에 등록된 클랜들
            async with db.execute('''
                SELECT clan_name, 'local' as source 
                FROM clan_teams 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY clan_name
            ''', (guild_id,)) as cursor:
                local_clans = await cursor.fetchall()
            
            # 2. 글로벌 공유 클랜들 (사용 빈도순)
            async with db.execute('''
                SELECT clan_name, 'global' as source 
                FROM global_shared_clans 
                WHERE clan_name NOT IN (
                    SELECT clan_name FROM clan_teams WHERE guild_id = ?
                )
                ORDER BY usage_count DESC, clan_name
                LIMIT 50
            ''', (guild_id,)) as cursor:
                global_clans = await cursor.fetchall()
            
            # 결과 조합
            all_clans = []
            
            # 로컬 클랜들 먼저 (우선순위)
            for clan_name, source in local_clans:
                all_clans.append({
                    'name': clan_name,
                    'value': clan_name,
                    'source': source,
                    'display': f"🏠 {clan_name} (우리서버)"
                })
            
            # 글로벌 클랜들
            for clan_name, source in global_clans:
                all_clans.append({
                    'name': clan_name,
                    'value': clan_name,
                    'source': source,
                    'display': f"🌐 {clan_name}"
                })
            
            return all_clans

    async def get_our_clan_name(self, guild_id: str) -> Optional[str]:
        """현재 서버의 대표 클랜명 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            # 가장 최근에 등록된 클랜을 대표 클랜으로 사용
            async with db.execute('''
                SELECT clan_name 
                FROM clan_teams 
                WHERE guild_id = ? AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            ''', (guild_id,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else None

    async def create_enhanced_scrim(self, scrim_data: Dict[str, Any]) -> str:
        """향상된 스크림 모집 생성"""
        
        # 재시도 로직 추가
        for attempt in range(3):
            try:
                async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                    await db.execute('PRAGMA journal_mode=WAL')
                    await db.execute('PRAGMA synchronous=NORMAL')  # 성능 개선
                    await db.execute('PRAGMA busy_timeout=30000')   # 30초 대기
                    
                    scrim_id = str(uuid.uuid4())
                    created_at = datetime.now(timezone.utc).isoformat()
                    
                    # 트랜잭션 시작
                    await db.execute('BEGIN IMMEDIATE')
                    
                    try:
                        # 기본 스크림 정보 저장
                        await db.execute('''
                            INSERT INTO inter_guild_scrims 
                            (id, guild_id, title, content, tier_range, opponent_team, 
                            scrim_date, deadline_date, channel_id, max_participants, 
                            status, created_by, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            scrim_id, scrim_data['guild_id'], scrim_data['title'],
                            scrim_data.get('description', ''), scrim_data['tier_range'], 
                            scrim_data['opponent_team'], scrim_data['primary_date'],
                            scrim_data['deadline_date'], scrim_data['channel_id'],
                            50, 'active', scrim_data['created_by'], created_at
                        ))
                        
                        # 시간 조합들 배치 저장
                        time_data = []
                        for time_combo in scrim_data['time_combinations']:
                            time_data.append((
                                scrim_id, time_combo['date'], time_combo['time'],
                                time_combo['date_display'], time_combo.get('is_custom', False)
                            ))
                        
                        await db.executemany('''
                            INSERT INTO scrim_time_slots 
                            (scrim_id, date_str, time_slot, date_display, is_custom_time)
                            VALUES (?, ?, ?, ?, ?)
                        ''', time_data)
                        
                        # 글로벌 클랜 업데이트
                        now = datetime.now(timezone.utc).isoformat()
                        await db.execute('''
                            INSERT OR REPLACE INTO global_shared_clans 
                            (clan_name, origin_guild_id, last_used, usage_count)
                            VALUES (?, ?, ?, 
                                    COALESCE((SELECT usage_count FROM global_shared_clans WHERE clan_name = ?), 0) + 1)
                        ''', (scrim_data['opponent_team'], scrim_data['guild_id'], now, scrim_data['opponent_team']))
                        
                        await db.commit()
                        return scrim_id
                        
                    except Exception as e:
                        await db.rollback()
                        raise e
                        
            except aiosqlite.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 0.5초, 1초 대기
                    continue
                raise e
            except Exception as e:
                raise e
    
        raise Exception("데이터베이스 락 해제 실패 - 잠시 후 다시 시도해주세요")

    async def update_global_clan_usage(self, clan_name: str, guild_id: str):
        """글로벌 클랜 사용 횟수 업데이트"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now(timezone.utc).isoformat()
            
            await db.execute('''
                INSERT OR REPLACE INTO global_shared_clans 
                (clan_name, origin_guild_id, last_used, usage_count)
                VALUES (
                    ?, ?, ?, 
                    COALESCE((SELECT usage_count FROM global_shared_clans WHERE clan_name = ?), 0) + 1
                )
            ''', (clan_name, guild_id, now, clan_name))
            
            await db.commit()

    async def get_scrim_info(self, scrim_id: str) -> Optional[Dict[str, Any]]:
        """스크림 기본 정보 조회 (마감기한 체크용)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT id, guild_id, title, description, tier_range, opponent_team,
                        primary_date, deadline_date, channel_id, created_by, status,
                        created_at, updated_at
                    FROM inter_guild_scrims 
                    WHERE id = ?
                ''', (scrim_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        columns = [description[0] for description in cursor.description]
                        return dict(zip(columns, row))
                    return None
        except Exception as e:
            print(f"❌ get_scrim_info 오류: {e}")
            return None

    async def get_scrim_time_slots(self, scrim_id: str) -> List[Dict[str, Any]]:
        """스크림의 시간 조합 목록 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT id, date_str, time_slot, date_display, is_custom_time
                FROM scrim_time_slots 
                WHERE scrim_id = ?
                ORDER BY date_str, time_slot
            ''', (scrim_id,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def add_position_participant(self, scrim_id: str, time_slot_id: int, 
                                     user_id: str, username: str, position: str) -> bool:
        """포지션별 참가자 추가"""
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.now(timezone.utc).isoformat()
            
            try:
                await db.execute('''
                    INSERT OR REPLACE INTO scrim_position_participants 
                    (scrim_id, time_slot_id, user_id, username, position, status, joined_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'joined', ?, ?)
                ''', (scrim_id, time_slot_id, user_id, username, position, now, now))
                
                await db.commit()
                return True
            except Exception as e:
                print(f"❌ 참가자 추가 실패: {e}")
                return False

    async def remove_position_participant(self, scrim_id: str, time_slot_id: int, 
                                        user_id: str, position: str) -> bool:
        """포지션별 참가자 제거"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    DELETE FROM scrim_position_participants 
                    WHERE scrim_id = ? AND time_slot_id = ? AND user_id = ? AND position = ?
                ''', (scrim_id, time_slot_id, user_id, position))
                
                await db.commit()
                return True
            except Exception as e:
                print(f"❌ 참가자 제거 실패: {e}")
                return False

    async def get_position_participants(self, time_slot_id: int) -> Dict[str, List[Dict]]:
        """특정 시간대의 포지션별 참가자 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT user_id, username, position, joined_at
                FROM scrim_position_participants 
                WHERE time_slot_id = ? AND status = 'joined'
                ORDER BY joined_at
            ''', (time_slot_id,)) as cursor:
                rows = await cursor.fetchall()
                
                # 포지션별로 그룹화
                participants = {'탱커': [], '딜러': [], '힐러': [], '플렉스': []}
                for user_id, username, position, joined_at in rows:
                    participants[position].append({
                        'user_id': user_id,
                        'username': username,
                        'joined_at': joined_at
                    })
                
                return participants

    async def get_user_participation_status(self, scrim_id: str, user_id: str) -> Dict[str, Any]:
        """사용자의 스크림 참가 현황 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('''
                SELECT ts.id as time_slot_id, ts.date_display, ts.time_slot, 
                       spp.position, spp.joined_at
                FROM scrim_time_slots ts
                LEFT JOIN scrim_position_participants spp ON ts.id = spp.time_slot_id 
                    AND spp.user_id = ? AND spp.status = 'joined'
                WHERE ts.scrim_id = ?
                ORDER BY ts.date_str, ts.time_slot
            ''', (user_id, scrim_id)) as cursor:
                rows = await cursor.fetchall()
                
                participation = {}
                for time_slot_id, date_display, time_slot, position, joined_at in rows:
                    key = f"{date_display} {time_slot}"
                    if key not in participation:
                        participation[key] = {
                            'time_slot_id': time_slot_id,
                            'positions': [],
                            'joined': False
                        }
                    
                    if position:
                        participation[key]['positions'].append(position)
                        participation[key]['joined'] = True
                
                return participation

    async def get_enhanced_scrim_summary(self, scrim_id: str) -> Dict[str, Any]:
        """향상된 스크림 요약 정보 (참가자 현황 포함)"""
        async with aiosqlite.connect(self.db_path) as db:
            # 기본 스크림 정보
            async with db.execute('''
                SELECT * FROM inter_guild_scrims WHERE id = ?
            ''', (scrim_id,)) as cursor:
                scrim_row = await cursor.fetchone()
                if not scrim_row:
                    return None
                
                columns = [description[0] for description in cursor.description]
                scrim_data = dict(zip(columns, scrim_row))
            
            # 시간대별 참가자 현황
            time_slots = await self.get_scrim_time_slots(scrim_id)
            for slot in time_slots:
                slot['participants'] = await self.get_position_participants(slot['id'])
                slot['total_participants'] = sum(len(p) for p in slot['participants'].values())
            
            scrim_data['time_slots'] = time_slots
            scrim_data['total_time_slots'] = len(time_slots)
            
            return scrim_data

    async def get_tier_eligible_users(self, guild_id: str, tier_range: str) -> List[Dict[str, str]]:
        """티어 범위에 해당하는 사용자 목록 조회"""
        # 티어 계층 정의
        tier_hierarchy = {
            "언랭": 0, "브론즈": 1, "실버": 2, "골드": 3,
            "플래티넘": 4, "다이아": 5, "마스터": 6, "그마": 7, "챔피언": 8
        }
        
        # 티어 범위 파싱
        if "~" in tier_range:
            min_tier, max_tier = tier_range.split("~")
        else:
            min_tier = max_tier = tier_range
        
        min_level = tier_hierarchy.get(min_tier, 0)
        max_level = tier_hierarchy.get(max_tier, 8)
        
        async with aiosqlite.connect(self.db_path) as db:
            # 등록된 사용자 중 해당 티어 범위의 사용자들 조회
            placeholders = ', '.join(['?' for _ in range(min_level, max_level + 1)])
            tier_names = [tier for tier, level in tier_hierarchy.items() 
                         if min_level <= level <= max_level]
            
            if not tier_names:
                return []
            
            query = f'''
                SELECT user_id, username, battle_tag, current_season_tier
                FROM registered_users 
                WHERE guild_id = ? AND current_season_tier IN ({placeholders})
                ORDER BY username
            '''
            
            async with db.execute(query, [guild_id] + tier_names) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def send_scrim_notification_to_users(self, eligible_users: List[Dict], scrim_data: Dict) -> int:
        """해당 티어 사용자들에게 스크림 알림 발송"""
        success_count = 0
        
        for user_data in eligible_users:
            try:
                user_id = int(user_data['user_id'])
                # 실제 DM 발송은 bot 객체가 필요하므로 여기서는 카운트만
                # 실제 구현에서는 bot.get_user(user_id).send() 사용
                success_count += 1
            except Exception as e:
                print(f"❌ DM 발송 실패 (User ID: {user_data.get('user_id')}): {e}")
        
        return success_count

    async def is_scrim_finalized(self, scrim_id: str) -> bool:
        """스크림이 마감되었는지 확인"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT COUNT(*) FROM scrim_time_slots 
                    WHERE scrim_id = ? AND finalized = TRUE
                ''', (scrim_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] > 0 if row else False
        except Exception as e:
            print(f"❌ is_scrim_finalized 오류: {e}")
            return False

    async def finalize_time_slot(self, scrim_id: str, time_slot_id: int) -> bool:
        """특정 시간대를 확정 상태로 변경"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 해당 시간대를 확정 상태로 변경
                await db.execute('''
                    UPDATE scrim_time_slots 
                    SET finalized = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE scrim_id = ? AND id = ?
                ''', (scrim_id, time_slot_id))
                
                # 스크림 전체 상태를 '부분 마감'으로 변경
                await db.execute('''
                    UPDATE inter_guild_scrims 
                    SET status = 'partially_closed', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (scrim_id,))
                
                await db.commit()
                return True
                
        except Exception as e:
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute('''
                        UPDATE scrim_time_slots 
                        SET finalized = TRUE
                        WHERE scrim_id = ? AND id = ?
                    ''', (scrim_id, time_slot_id))
                    
                    await db.execute('''
                        UPDATE inter_guild_scrims 
                        SET status = 'partially_closed'
                        WHERE id = ?
                    ''', (scrim_id,))
                    
                    await db.commit()
                    return True
            except Exception as e2:
                print(f"❌ finalize_time_slot 오류: {e2}")
                return False

    async def is_time_slot_finalized(self, time_slot_id: int) -> bool:
        """특정 시간대가 확정되었는지 확인"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT finalized FROM scrim_time_slots 
                    WHERE id = ?
                ''', (time_slot_id,)) as cursor:
                    row = await cursor.fetchone()
                    return bool(row[0]) if row else False
        except Exception as e:
            print(f"❌ is_time_slot_finalized 오류: {e}")
            return False

    async def get_finalized_time_slots(self, scrim_id: str) -> List[Dict[str, Any]]:
        """확정된 시간대 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT id, scrim_id, date_str, time_slot, date_display, is_custom_time, finalized
                    FROM scrim_time_slots 
                    WHERE scrim_id = ? AND finalized = TRUE
                    ORDER BY date_str, time_slot
                ''', (scrim_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"❌ get_finalized_time_slots 오류: {e}")
            return []

    async def get_non_finalized_time_slots(self, scrim_id: str) -> List[Dict[str, Any]]:
        """아직 확정되지 않은 시간대 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT id, scrim_id, date_str, time_slot, date_display, is_custom_time, 
                        COALESCE(finalized, FALSE) as finalized
                    FROM scrim_time_slots 
                    WHERE scrim_id = ? AND COALESCE(finalized, FALSE) = FALSE
                    ORDER BY date_str, time_slot
                ''', (scrim_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"❌ get_non_finalized_time_slots 오류: {e}")
            return []

    async def update_scrim_time_slots_table(self):
        """기존 테이블에 finalized 컬럼 추가 (마이그레이션용)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # finalized 컬럼이 존재하는지 확인
                async with db.execute("PRAGMA table_info(scrim_time_slots)") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    
                    if 'finalized' not in column_names:
                        await db.execute('''
                            ALTER TABLE scrim_time_slots 
                            ADD COLUMN finalized BOOLEAN DEFAULT FALSE
                        ''')
                        print("✅ scrim_time_slots 테이블에 finalized 컬럼이 추가되었습니다.")
                    
                    if 'updated_at' not in column_names:
                        await db.execute('''
                            ALTER TABLE scrim_time_slots 
                            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ''')
                        print("✅ scrim_time_slots 테이블에 updated_at 컬럼이 추가되었습니다.")
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ update_scrim_time_slots_table 오류: {e}")
            return False

    async def get_scrim_finalization_summary(self, scrim_id: str) -> Dict[str, Any]:
        """스크림 마감 현황 요약 정보"""
        try:
            scrim_info = await self.get_scrim_info(scrim_id)
            if not scrim_info:
                return None
            
            finalized_slots = await self.get_finalized_time_slots(scrim_id)
            non_finalized_slots = await self.get_non_finalized_time_slots(scrim_id)
            
            # 확정된 시간대별 참가자 수 계산
            finalized_summary = []
            for slot in finalized_slots:
                participants = await self.get_position_participants(slot['id'])
                total_count = sum(len(pos_list) for pos_list in participants.values())
                finalized_summary.append({
                    'slot': slot,
                    'participant_count': total_count,
                    'participants': participants
                })
            
            return {
                'scrim_info': scrim_info,
                'finalized_count': len(finalized_slots),
                'pending_count': len(non_finalized_slots),
                'total_slots': len(finalized_slots) + len(non_finalized_slots),
                'finalized_slots': finalized_summary,
                'pending_slots': non_finalized_slots,
                'is_fully_finalized': len(non_finalized_slots) == 0,
                'is_partially_finalized': len(finalized_slots) > 0
            }
            
        except Exception as e:
            print(f"❌ get_scrim_finalization_summary 오류: {e}")
            return None

    async def get_scrim_admin_info(self, scrim_id: str) -> Optional[Dict[str, Any]]:
        """스크림 관리자 정보 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT created_by, title, opponent_team, guild_id
                    FROM inter_guild_scrims 
                    WHERE id = ?
                ''', (scrim_id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'admin_id': row[0],
                            'title': row[1], 
                            'opponent_team': row[2],
                            'guild_id': row[3]
                        }
                    return None
        except Exception as e:
            print(f"❌ get_scrim_admin_info 오류: {e}")
            return None

    async def update_recruitment_message_info(self, recruitment_id: str, message_id: str, channel_id: str):
        """모집 공지의 메시지 ID와 채널 ID를 업데이트합니다."""
        try:
            query = """
            UPDATE scrim_recruitments
            SET message_id = ?, channel_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(query, (message_id, channel_id, recruitment_id))
                await db.commit()
                print(f"✅ 메시지 정보 업데이트 성공: {recruitment_id}")
                return True
                
        except Exception as e:
            print(f"❌ 모집 메시지 정보 업데이트 실패: {e}")
            return False
        
    async def get_eligible_users_for_balancing(self, guild_id: str, min_games: int = 3) -> List[dict]:
        """
        팀 밸런싱이 가능한 유저 목록 조회
        최소 게임 수를 충족하고 등록된 유저만 반환
        """
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    ru.user_id,
                    ru.username,
                    ru.main_position,
                    COALESCE(us.total_games, 0) as total_games,
                    COALESCE(us.total_wins, 0) as total_wins,
                    COALESCE(us.tank_games, 0) as tank_games,
                    COALESCE(us.tank_wins, 0) as tank_wins,
                    COALESCE(us.dps_games, 0) as dps_games,
                    COALESCE(us.dps_wins, 0) as dps_wins,
                    COALESCE(us.support_games, 0) as support_games,
                    COALESCE(us.support_wins, 0) as support_wins,
                    ru.current_season_tier
                FROM registered_users ru
                LEFT JOIN user_statistics us ON ru.user_id = us.user_id AND ru.guild_id = us.guild_id
                WHERE ru.guild_id = ? 
                AND ru.is_active = 1
                AND COALESCE(us.total_games, 0) >= ?
                ORDER BY us.total_games DESC, ru.username ASC
            ''', (guild_id, min_games)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_user_position_detailed_stats(self, user_id: str, guild_id: str) -> dict:
        """
        특정 유저의 포지션별 상세 통계 조회
        """
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            # 기본 통계
            async with db.execute('''
                SELECT 
                    total_games, total_wins,
                    tank_games, tank_wins,
                    dps_games, dps_wins,
                    support_games, support_wins,
                    last_updated
                FROM user_statistics 
                WHERE user_id = ? AND guild_id = ?
            ''', (user_id, guild_id)) as cursor:
                stats_row = await cursor.fetchone()
                
                if not stats_row:
                    return {
                        'total_games': 0, 'total_wins': 0,
                        'tank_games': 0, 'tank_wins': 0,
                        'dps_games': 0, 'dps_wins': 0, 
                        'support_games': 0, 'support_wins': 0,
                        'last_updated': None,
                        'recent_games': 0, 'recent_wins': 0, 'recent_winrate': 0.0
                    }
                
                columns = [description[0] for description in cursor.description]
                stats = dict(zip(columns, stats_row))
                
                # 최근 10경기 성과 (추가 정보)
                async with db.execute('''
                    SELECT won, position, match_date
                    FROM match_participants mp
                    JOIN match_results mr ON mp.match_id = mr.id
                    WHERE mp.user_id = ? AND mr.guild_id = ?
                    ORDER BY mr.match_date DESC
                    LIMIT 10
                ''', (user_id, guild_id)) as recent_cursor:
                    recent_matches = await recent_cursor.fetchall()
                    
                    recent_wins = sum(1 for match in recent_matches if match[0])
                    recent_games = len(recent_matches)
                    
                    stats['recent_games'] = recent_games
                    stats['recent_wins'] = recent_wins
                    stats['recent_winrate'] = recent_wins / max(recent_games, 1)
                    
                return stats

    async def get_users_head_to_head_records(self, user_ids: List[str], guild_id: str) -> List[dict]:
        """
        선택된 유저들 간의 모든 상대전적 조회
        """
        if len(user_ids) < 2:
            return []
        
        # user_ids를 문자열로 변환하여 SQL IN 절에 사용
        user_ids_placeholder = ','.join('?' * len(user_ids))
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute(f'''
                SELECT 
                    um.user1_id,
                    um.user2_id,
                    um.user1_wins,
                    um.user2_wins,
                    um.total_matches,
                    um.last_match_date,
                    ru1.username as user1_name,
                    ru2.username as user2_name
                FROM user_matchups um
                JOIN registered_users ru1 ON um.user1_id = ru1.user_id AND ru1.guild_id = ?
                JOIN registered_users ru2 ON um.user2_id = ru2.user_id AND ru2.guild_id = ?
                WHERE um.user1_id IN ({user_ids_placeholder})
                AND um.user2_id IN ({user_ids_placeholder})
                AND um.total_matches >= 3
                ORDER BY um.total_matches DESC
            ''', [guild_id, guild_id] + user_ids + user_ids) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_users_teammate_records(self, user_ids: List[str], guild_id: str) -> List[dict]:
        """
        선택된 유저들 간의 팀메이트 조합 기록 조회
        """
        if len(user_ids) < 2:
            return []
        
        user_ids_placeholder = ','.join('?' * len(user_ids))
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute(f'''
                SELECT 
                    tc.user1_id,
                    tc.user2_id,
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN tc.won = 1 THEN 1 ELSE 0 END) as wins,
                    ru1.username as user1_name,
                    ru2.username as user2_name,
                    MAX(m.created_at) as last_match_date
                FROM teammate_combinations tc
                JOIN matches m ON tc.match_id = m.id
                JOIN registered_users ru1 ON tc.user1_id = ru1.user_id AND ru1.guild_id = ?
                JOIN registered_users ru2 ON tc.user2_id = ru2.user_id AND ru2.guild_id = ?
                WHERE tc.user1_id IN ({user_ids_placeholder})
                AND tc.user2_id IN ({user_ids_placeholder})
                AND m.guild_id = ?
                GROUP BY tc.user1_id, tc.user2_id
                HAVING total_matches >= 2
                ORDER BY total_matches DESC, wins DESC
            ''', [guild_id, guild_id] + user_ids + user_ids + [guild_id]) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                # 승률 계산 추가
                results = []
                for row in rows:
                    record = dict(zip(columns, row))
                    record['winrate'] = record['wins'] / max(record['total_matches'], 1)
                    results.append(record)
                    
                return results

    async def get_user_recent_performance_trend(self, user_id: str, guild_id: str, days: int = 30) -> dict:
        """
        유저의 최근 성과 트렌드 분석
        """
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_date_str = cutoff_date.isoformat()
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            # 최근 경기들 조회
            async with db.execute('''
                SELECT 
                    mp.won,
                    mp.position,
                    mr.match_date,
                    mr.winning_team,
                    mp.team
                FROM match_participants mp
                JOIN match_results mr ON mp.match_id = mr.id
                WHERE mp.user_id = ? 
                AND mr.guild_id = ?
                AND mr.match_date >= ?
                ORDER BY mr.match_date ASC
            ''', (user_id, guild_id, cutoff_date_str)) as cursor:
                recent_matches = await cursor.fetchall()
                
                if not recent_matches:
                    return {
                        'total_games': 0,
                        'total_wins': 0,
                        'winrate': 0.0,
                        'trend': 'stable',
                        'position_performance': {},
                        'streak': {'type': 'none', 'count': 0}
                    }
                
                # 기본 통계
                total_games = len(recent_matches)
                total_wins = sum(1 for match in recent_matches if match[0])
                winrate = total_wins / total_games
                
                # 포지션별 성과
                position_stats = {}
                for match in recent_matches:
                    position = match[1] if match[1] else '미설정'
                    if position not in position_stats:
                        position_stats[position] = {'games': 0, 'wins': 0}
                    position_stats[position]['games'] += 1
                    position_stats[position]['wins'] += match[0]
                
                # 각 포지션별 승률 계산
                for pos in position_stats:
                    position_stats[pos]['winrate'] = position_stats[pos]['wins'] / position_stats[pos]['games']
                
                # 연승/연패 계산
                streak = {'type': 'none', 'count': 0}
                if recent_matches:
                    current_streak = 0
                    last_result = recent_matches[-1][0]  # 가장 최근 경기 결과
                    
                    # 뒤에서부터 연속된 결과 카운트
                    for match in reversed(recent_matches):
                        if match[0] == last_result:
                            current_streak += 1
                        else:
                            break
                    
                    if current_streak >= 2:
                        streak = {
                            'type': 'win' if last_result else 'lose',
                            'count': current_streak
                        }
                
                # 트렌드 분석 (최근 5경기 vs 이전 5경기)
                trend = 'stable'
                if total_games >= 6:
                    recent_5 = recent_matches[-5:]
                    previous_5 = recent_matches[-10:-5] if len(recent_matches) >= 10 else recent_matches[:-5]
                    
                    recent_5_winrate = sum(1 for m in recent_5 if m[0]) / len(recent_5)
                    previous_winrate = sum(1 for m in previous_5 if m[0]) / len(previous_5) if previous_5 else 0.5
                    
                    if recent_5_winrate - previous_winrate > 0.2:
                        trend = 'improving'
                    elif previous_winrate - recent_5_winrate > 0.2:
                        trend = 'declining'
                
                return {
                    'total_games': total_games,
                    'total_wins': total_wins,
                    'winrate': winrate,
                    'trend': trend,
                    'position_performance': position_stats,
                    'streak': streak
                }

    async def get_server_position_distribution(self, guild_id: str) -> dict:
        """
        서버 내 포지션 분포 현황 조회 (밸런싱 참고용)
        """
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT 
                    main_position,
                    COUNT(*) as count,
                    AVG(CASE 
                        WHEN us.total_games > 0 THEN CAST(us.total_wins AS FLOAT) / us.total_games 
                        ELSE 0 
                    END) as avg_winrate
                FROM registered_users ru
                LEFT JOIN user_statistics us ON ru.user_id = us.user_id AND ru.guild_id = us.guild_id
                WHERE ru.guild_id = ? 
                AND ru.is_active = 1
                AND COALESCE(us.total_games, 0) >= 3
                GROUP BY main_position
            ''', (guild_id,)) as cursor:
                rows = await cursor.fetchall()
                
                distribution = {}
                total_players = 0
                
                for row in rows:
                    position = row[0] if row[0] else '미설정'
                    count = row[1]
                    avg_winrate = row[2] if row[2] else 0.0
                    
                    distribution[position] = {
                        'count': count,
                        'percentage': 0.0,  # 나중에 계산
                        'avg_winrate': avg_winrate
                    }
                    total_players += count
                
                # 퍼센트 계산
                for position in distribution:
                    distribution[position]['percentage'] = (distribution[position]['count'] / total_players) * 100
                
                return {
                    'total_eligible_players': total_players,
                    'distribution': distribution
                }

    async def get_nickname_format(self, guild_id: str) -> dict:
        """서버의 닉네임 포맷 설정 조회"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            async with db.execute('''
                SELECT format_template, required_fields 
                FROM nickname_format_settings 
                WHERE guild_id = ?
            ''', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                
                if row:
                    import json
                    return {
                        'format_template': row[0],
                        'required_fields': json.loads(row[1]) if row[1] else []
                    }
                else:
                    # 기본 포맷 반환 (기존 방식)
                    return {
                        'format_template': '{battle_tag}/{position}/{tier}',
                        'required_fields': ['battle_tag', 'position', 'tier']
                    }

    async def set_nickname_format(self, guild_id: str, format_template: str, required_fields: list) -> bool:
        """서버의 닉네임 포맷 설정 저장"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                import json
                await db.execute('''
                    INSERT INTO nickname_format_settings (guild_id, format_template, required_fields)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        format_template = excluded.format_template,
                        required_fields = excluded.required_fields
                ''', (guild_id, format_template, json.dumps(required_fields)))
                
                await db.commit()
                return True
            except Exception as e:
                print(f"❌ 닉네임 포맷 설정 실패: {e}")
                return False

    def _generate_nickname_from_template(self, template: str, data: dict) -> str:
        """템플릿 기반 닉네임 생성
        
        Args:
            template: 예) "{nickname} {birth_year} {tier}"
            data: 예) {"nickname": "헤븐", "birth_year": "00", "tier": "그마"}
        
        Returns:
            생성된 닉네임: "헤븐 00 그마"
        """
        try:
            # 사용 가능한 필드 매핑
            field_map = {
                'nickname': data.get('nickname', ''),
                'battle_tag': data.get('battle_tag', ''),
                'birth_year': data.get('birth_year', ''),
                'position': self._get_position_short(data.get('position', '')),
                'tier': data.get('tier', ''),
                'previous_tier': data.get('previous_tier', ''),
                'highest_tier': data.get('highest_tier', '')
            }
            
            # 템플릿 치환
            nickname = template
            for field_name, field_value in field_map.items():
                nickname = nickname.replace(f'{{{field_name}}}', str(field_value))
            
            # 최대 32자 제한 (Discord 닉네임 제한)
            if len(nickname) > 32:
                nickname = nickname[:32]
            
            return nickname.strip()
            
        except Exception as e:
            print(f"❌ 닉네임 생성 실패: {e}")
            # 실패 시 배틀태그 반환
            return data.get('battle_tag', 'Unknown')[:32]

    def _get_position_short(self, position: str) -> str:
        """포지션 축약"""
        position_map = {
            "탱커": "탱",
            "딜러": "딜",
            "힐러": "힐",
            "탱커 & 딜러": "탱딜",
            "탱커 & 힐러": "탱힐",
            "딜러 & 힐러": "딜힐",
            "탱커 & 딜러 & 힐러": "탱딜힐"
        }
        return position_map.get(position, position)

    async def _update_user_nickname(self, discord_member: discord.Member, 
                                main_position: str, current_tier: str, 
                                battle_tag: str, birth_year: str = None) -> str:
        """유저 닉네임 자동 변경 (템플릿 기반)"""
        try:
            guild_id = str(discord_member.guild.id)
            
            # 서버 닉네임 포맷 가져오기
            format_settings = await self.get_nickname_format(guild_id)
            template = format_settings['format_template']
            
            # 배틀태그에서 닉네임 추출 (# 앞부분)
            nickname = battle_tag.split('#')[0] if '#' in battle_tag else battle_tag
            
            # 데이터 준비
            nickname_data = {
                'nickname': nickname,
                'battle_tag': battle_tag,
                'birth_year': birth_year or '',
                'position': main_position,
                'tier': current_tier,
                'previous_tier': '',  
                'highest_tier': ''    
            }
            
            # 템플릿으로 닉네임 생성
            new_nickname = self._generate_nickname_from_template(template, nickname_data)
            
            # Discord 닉네임 변경 시도
            old_nickname = discord_member.display_name
            
            try:
                await discord_member.edit(nick=new_nickname)
                return f"✅ 닉네임 변경: {old_nickname} → {new_nickname}"
            except discord.Forbidden:
                return f"❌ 닉네임 변경 실패: 권한 부족 (봇 역할이 대상 유저보다 낮음)"
            except discord.HTTPException as e:
                return f"❌ 닉네임 변경 실패: {str(e)}"
                
        except Exception as e:
            return f"❌ 닉네임 변경 중 오류: {str(e)}"

    async def approve_user_application_with_nickname(self, guild_id: str, user_id: str, admin_id: str, 
                                                    discord_member: discord.Member, admin_note: str = None) -> tuple[bool, str]:
        """유저 신청 승인 및 닉네임 자동 변경 (생년 포함)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 신청 정보 가져오기 (birth_year 포함)
            async with db.execute('''
                SELECT guild_id, user_id, username, entry_method, battle_tag, 
                    main_position, previous_season_tier, current_season_tier, 
                    highest_tier, birth_year
                FROM user_applications 
                WHERE guild_id = ? AND user_id = ? AND status = 'pending'
            ''', (guild_id, user_id)) as cursor:
                application = await cursor.fetchone()
                if not application:
                    return False, "신청을 찾을 수 없습니다."
            
            # 신청 상태 업데이트
            await db.execute('''
                UPDATE user_applications 
                SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP, 
                    reviewed_by = ?, admin_note = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (admin_id, admin_note, guild_id, user_id))
            
            # registered_users에 추가
            await db.execute('''
                INSERT INTO registered_users 
                (guild_id, user_id, username, entry_method, battle_tag, main_position, 
                previous_season_tier, current_season_tier, highest_tier, birth_year,
                approved_by, is_active, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    username = excluded.username,
                    entry_method = excluded.entry_method,
                    battle_tag = excluded.battle_tag,
                    main_position = excluded.main_position,
                    previous_season_tier = excluded.previous_season_tier,
                    current_season_tier = excluded.current_season_tier,
                    highest_tier = excluded.highest_tier,
                    birth_year = excluded.birth_year,
                    approved_by = excluded.approved_by,
                    is_active = TRUE,
                    registered_at = CURRENT_TIMESTAMP
            ''', (application[0], application[1], application[2], application[3], 
                application[4], application[5], application[6], application[7], 
                application[8], application[9], admin_id))
            
            # user_battle_tags에도 배틀태그 저장
            await db.execute('''
                INSERT INTO user_battle_tags 
                (guild_id, user_id, battle_tag, account_type, is_primary)
                VALUES (?, ?, ?, 'main', TRUE)
                ON CONFLICT(guild_id, user_id, battle_tag) DO NOTHING
            ''', (guild_id, user_id, application[4]))
            
            await db.commit()
            
            # 닉네임 변경
            nickname_result = await self._update_user_nickname(
                discord_member, 
                application[5],  # main_position
                application[7],  # current_season_tier  
                application[4],  # battle_tag
                application[9]   # birth_year
            )
            
            # 역할 변경
            role_result = await self._update_user_roles_conditional(discord_member, guild_id)
            
            combined_result = f"{nickname_result}\n{role_result}"
            
            return True, combined_result

    async def add_battle_tag(self, guild_id: str, user_id: str, battle_tag: str, 
                            account_type: str = 'sub', rank_info: dict = None) -> bool:
        """배틀태그 추가"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 이미 존재하는지 확인
                async with db.execute('''
                    SELECT COUNT(*) FROM user_battle_tags 
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (guild_id, user_id, battle_tag)) as cursor:
                    exists = (await cursor.fetchone())[0] > 0
                    
                if exists:
                    return False
                
                # 첫 번째 배틀태그면 자동으로 primary 설정
                async with db.execute('''
                    SELECT COUNT(*) FROM user_battle_tags 
                    WHERE guild_id = ? AND user_id = ?
                ''', (guild_id, user_id)) as cursor:
                    is_first = (await cursor.fetchone())[0] == 0
                
                # JSON 변환
                rank_json = json.dumps(rank_info) if rank_info else None
                
                await db.execute('''
                    INSERT INTO user_battle_tags 
                    (guild_id, user_id, battle_tag, account_type, is_primary, rank_info)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (guild_id, user_id, battle_tag, account_type, is_first, rank_json))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 배틀태그 추가 실패: {e}")
            return False


    async def get_user_battle_tags(self, guild_id: str, user_id: str) -> List[Dict]:
        """유저의 모든 배틀태그 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT battle_tag, account_type, is_primary, rank_info, created_at
                    FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY is_primary DESC, created_at ASC
                ''', (guild_id, user_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    result = []
                    for row in rows:
                        rank_info = json.loads(row[3]) if row[3] else None
                        result.append({
                            'battle_tag': row[0],
                            'account_type': row[1],
                            'is_primary': bool(row[2]),
                            'rank_info': rank_info,
                            'created_at': row[4]
                        })
                    
                    return result
        except Exception as e:
            print(f"❌ 배틀태그 조회 실패: {e}")
            return []


    async def get_primary_battle_tag(self, guild_id: str, user_id: str) -> Optional[str]:
        """주계정 배틀태그 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT battle_tag FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ? AND is_primary = TRUE
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            print(f"❌ 주계정 조회 실패: {e}")
            return None


    async def delete_battle_tag(self, guild_id: str, user_id: str, battle_tag: str) -> bool:
        """배틀태그 삭제"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # primary 계정인지 확인
                async with db.execute('''
                    SELECT is_primary FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (guild_id, user_id, battle_tag)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return False
                    was_primary = bool(row[0])
                
                # 삭제
                await db.execute('''
                    DELETE FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (guild_id, user_id, battle_tag))
                
                # primary였다면 다른 계정을 primary로 승격
                if was_primary:
                    await db.execute('''
                        UPDATE user_battle_tags
                        SET is_primary = TRUE
                        WHERE guild_id = ? AND user_id = ?
                        AND id = (
                            SELECT id FROM user_battle_tags
                            WHERE guild_id = ? AND user_id = ?
                            ORDER BY account_type = 'main' DESC, created_at ASC
                            LIMIT 1
                        )
                    ''', (guild_id, user_id, guild_id, user_id))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 배틀태그 삭제 실패: {e}")
            return False


    async def set_primary_battle_tag(self, guild_id: str, user_id: str, battle_tag: str) -> bool:
        """주계정 설정"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 해당 배틀태그 존재 확인
                async with db.execute('''
                    SELECT COUNT(*) FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (guild_id, user_id, battle_tag)) as cursor:
                    exists = (await cursor.fetchone())[0] > 0
                    
                if not exists:
                    return False
                
                # 기존 primary 해제
                await db.execute('''
                    UPDATE user_battle_tags
                    SET is_primary = FALSE
                    WHERE guild_id = ? AND user_id = ?
                ''', (guild_id, user_id))
                
                # 새 primary 설정
                await db.execute('''
                    UPDATE user_battle_tags
                    SET is_primary = TRUE
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (guild_id, user_id, battle_tag))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 주계정 설정 실패: {e}")
            return False


    async def search_battle_tag_owner(self, guild_id: str, battle_tag: str) -> Optional[Dict]:
        """배틀태그로 소유자 검색 (역검색)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT u.user_id, u.username, t.account_type, t.is_primary
                    FROM user_battle_tags t
                    JOIN registered_users u ON t.user_id = u.user_id AND t.guild_id = u.guild_id
                    WHERE t.guild_id = ? AND t.battle_tag = ?
                ''', (guild_id, battle_tag)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'user_id': row[0],
                            'username': row[1],
                            'account_type': row[2],
                            'is_primary': bool(row[3])
                        }
                    return None
        except Exception as e:
            print(f"❌ 배틀태그 소유자 검색 실패: {e}")
            return None


    async def update_battle_tag_rank_info(self, guild_id: str, user_id: str, 
                                        battle_tag: str, rank_info: dict) -> bool:
        """배틀태그 랭크 정보 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                rank_json = json.dumps(rank_info) if rank_info else None
                
                await db.execute('''
                    UPDATE user_battle_tags
                    SET rank_info = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                ''', (rank_json, guild_id, user_id, battle_tag))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 랭크 정보 업데이트 실패: {e}")
            return False

    async def migrate_battle_tags_to_new_table(self):
        """기존 registered_users.battle_tag → user_battle_tags 마이그레이션"""
        try:
            print("=" * 60)
            print("🔍 [마이그레이션] 시작...")
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 1️⃣ 테이블 존재 확인
                print("📋 [마이그레이션] 1단계: 테이블 존재 확인")
                async with db.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('user_battle_tags', 'registered_users')
                    ORDER BY name
                ''') as cursor:
                    tables = await cursor.fetchall()
                    table_names = [row[0] for row in tables]
                    print(f"   존재하는 테이블: {table_names}")
                    
                    if 'user_battle_tags' not in table_names:
                        print("❌ [마이그레이션] user_battle_tags 테이블이 없습니다!")
                        return False
                        
                    if 'registered_users' not in table_names:
                        print("❌ [마이그레이션] registered_users 테이블이 없습니다!")
                        return False
                
                # 2️⃣ registered_users 컬럼 확인
                print("📋 [마이그레이션] 2단계: registered_users 컬럼 확인")
                async with db.execute('PRAGMA table_info(registered_users)') as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]
                    print(f"   registered_users 컬럼: {column_names}")
                    
                    if 'battle_tag' not in column_names:
                        print("❌ [마이그레이션] battle_tag 컬럼이 없습니다!")
                        return False
                
                # 3️⃣ 마이그레이션 대상 조회
                print("📋 [마이그레이션] 3단계: 마이그레이션 대상 조회")
                async with db.execute('''
                    SELECT guild_id, user_id, battle_tag, username
                    FROM registered_users 
                    WHERE battle_tag IS NOT NULL 
                    AND battle_tag != ''
                    AND is_active = TRUE
                ''') as cursor:
                    all_users = await cursor.fetchall()
                    print(f"   registered_users에서 배틀태그 있는 유저: {len(all_users)}명")
                    
                    if all_users:
                        for user in all_users[:3]:  # 처음 3명만 출력
                            print(f"   - {user[3]} ({user[2]})")
                
                # 4️⃣ 기존 user_battle_tags 데이터 확인
                print("📋 [마이그레이션] 4단계: 기존 데이터 확인")
                async with db.execute('SELECT COUNT(*) FROM user_battle_tags') as cursor:
                    existing_count = (await cursor.fetchone())[0]
                    print(f"   user_battle_tags에 이미 있는 데이터: {existing_count}개")
                
                # 5️⃣ 마이그레이션 필요 여부 판단
                print("📋 [마이그레이션] 5단계: 중복 제외 대상 확인")
                async with db.execute('''
                    SELECT COUNT(*) FROM registered_users 
                    WHERE battle_tag IS NOT NULL AND battle_tag != ''
                    AND is_active = TRUE
                    AND NOT EXISTS (
                        SELECT 1 FROM user_battle_tags 
                        WHERE user_battle_tags.guild_id = registered_users.guild_id 
                        AND user_battle_tags.user_id = registered_users.user_id
                        AND user_battle_tags.battle_tag = registered_users.battle_tag
                    )
                ''') as cursor:
                    need_migration = (await cursor.fetchone())[0]
                    print(f"   실제 마이그레이션 필요: {need_migration}개")
                    
                    if need_migration == 0:
                        print("✅ [마이그레이션] 불필요 (이미 완료됨)")
                        return True
                
                # 6️⃣ 마이그레이션 실행
                print(f"📋 [마이그레이션] 6단계: {need_migration}개 데이터 이동 시작")
                async with db.execute('''
                    SELECT guild_id, user_id, battle_tag, username
                    FROM registered_users 
                    WHERE battle_tag IS NOT NULL AND battle_tag != ''
                    AND is_active = TRUE
                ''') as cursor:
                    users = await cursor.fetchall()
                
                migrated_count = 0
                for guild_id, user_id, battle_tag, username in users:
                    # 중복 체크
                    async with db.execute('''
                        SELECT COUNT(*) FROM user_battle_tags
                        WHERE guild_id = ? AND user_id = ? AND battle_tag = ?
                    ''', (guild_id, user_id, battle_tag)) as check_cursor:
                        already_exists = (await check_cursor.fetchone())[0] > 0
                    
                    if not already_exists:
                        print(f"   ✅ 추가: {username} ({battle_tag})")
                        await db.execute('''
                            INSERT INTO user_battle_tags 
                            (guild_id, user_id, battle_tag, account_type, is_primary)
                            VALUES (?, ?, ?, 'main', TRUE)
                        ''', (guild_id, user_id, battle_tag))
                        migrated_count += 1
                    else:
                        print(f"   ⏭️  건너뜀: {username} (이미 존재)")
                
                await db.commit()
                print("=" * 60)
                print(f"🎉 [마이그레이션] 완료: {migrated_count}개 계정 이동")
                print("=" * 60)
                return True
                
        except Exception as e:
            print("=" * 60)
            print(f"❌ [마이그레이션] 실패: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 60)
            return False


    async def _get_primary_battle_tag_for_nickname(self, guild_id: str, user_id: str) -> Optional[str]:
        """
        닉네임 생성용 주계정 배틀태그 조회
        1순위: user_battle_tags에서 is_primary=True
        2순위: user_battle_tags에서 account_type='main' 
        3순위: registered_users.battle_tag (폴백)
        """
        try:
            # 1순위: primary 배틀태그
            primary_tag = await self.get_primary_battle_tag(guild_id, user_id)
            if primary_tag:
                return primary_tag
            
            # 2순위: main 타입 배틀태그
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT battle_tag FROM user_battle_tags
                    WHERE guild_id = ? AND user_id = ? AND account_type = 'main'
                    ORDER BY created_at ASC
                    LIMIT 1
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return row[0]
                
                # 3순위: 폴백 (기존 registered_users.battle_tag)
                async with db.execute('''
                    SELECT battle_tag FROM registered_users
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        return row[0]
            
            return None
            
        except Exception as e:
            print(f"❌ 닉네임용 배틀태그 조회 실패: {e}")
            return None

    async def add_battle_tag_with_api(self, guild_id: str, user_id: str, battle_tag: str, 
                                    account_type: str = 'sub') -> tuple[bool, Optional[Dict]]:
        from utils.overwatch_api import OverwatchAPI
        
        # API 호출 시도
        rank_info = None
        profile_data = await OverwatchAPI.fetch_profile(battle_tag)

        print(f"[DEBUG] profile_data 존재 여부: {profile_data is not None}")
        
        if profile_data:
            rank_info = OverwatchAPI.parse_rank_info(profile_data)
            print(f"[DEBUG] rank_info: {rank_info}")
        
        # 배틀태그 추가 (API 실패해도 진행)
        success = await self.add_battle_tag(guild_id, user_id, battle_tag, account_type, rank_info)
        
        return success, rank_info


    async def refresh_battle_tag_rank(self, guild_id: str, user_id: str, battle_tag: str) -> Optional[Dict]:
        """
        배틀태그 랭크 정보 갱신
        
        Returns:
            갱신된 랭크 정보 dict 또는 None
        """
        from utils.overwatch_api import OverwatchAPI
        
        # API 호출
        profile_data = await OverwatchAPI.fetch_profile(battle_tag)
        
        if not profile_data:
            return None
        
        rank_info = OverwatchAPI.parse_rank_info(profile_data)
        
        if rank_info:
            # DB 업데이트
            await self.update_battle_tag_rank_info(guild_id, user_id, battle_tag, rank_info)
        
        return rank_info


    async def get_user_battle_tags_with_rank(self, guild_id: str, user_id: str) -> List[Dict]:
        """
        유저의 모든 배틀태그 조회 (랭크 정보 포함, 포맷팅 추가)
        
        Returns:
            배틀태그 목록 (rank_display 필드 추가)
        """
        from utils.overwatch_api import OverwatchAPI
        
        tags = await self.get_user_battle_tags(guild_id, user_id)
        
        for tag in tags:
            if tag['rank_info']:
                tag['rank_display'] = OverwatchAPI.format_rank_display(tag['rank_info'])
            else:
                tag['rank_display'] = "랭크 정보 없음"
        
        return tags

    async def get_battle_tag_log_settings(self, guild_id: str) -> Optional[Dict]:
        """배틀태그 로그 설정 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT log_channel_id, log_add, log_delete, log_primary_change, log_tier_change
                    FROM battle_tag_log_settings
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'log_channel_id': row[0],
                            'log_add': bool(row[1]),
                            'log_delete': bool(row[2]),
                            'log_primary_change': bool(row[3]),
                            'log_tier_change': bool(row[4])
                        }
                    return None
        except Exception as e:
            print(f"❌ 로그 설정 조회 실패: {e}")
            return None


    async def set_battle_tag_log_channel(self, guild_id: str, channel_id: str) -> bool:
        """로그 채널 설정"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # UPSERT (없으면 INSERT, 있으면 UPDATE)
                await db.execute('''
                    INSERT INTO battle_tag_log_settings (guild_id, log_channel_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id) 
                    DO UPDATE SET 
                        log_channel_id = excluded.log_channel_id,
                        updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, channel_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 로그 채널 설정 실패: {e}")
            return False


    async def update_battle_tag_log_toggle(self, guild_id: str, log_type: str, enabled: bool) -> bool:
        """로그 항목 토글"""
        try:
            valid_types = ['log_add', 'log_delete', 'log_primary_change', 'log_tier_change']
            if log_type not in valid_types:
                return False
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 설정이 없으면 먼저 생성
                await db.execute('''
                    INSERT INTO battle_tag_log_settings (guild_id)
                    VALUES (?)
                    ON CONFLICT(guild_id) DO NOTHING
                ''', (guild_id,))
                
                # 토글 업데이트
                query = f'''
                    UPDATE battle_tag_log_settings
                    SET {log_type} = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                '''
                await db.execute(query, (enabled, guild_id))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 로그 토글 업데이트 실패: {e}")
            return False


    async def reset_battle_tag_log_channel(self, guild_id: str) -> bool:
        """로그 채널 설정 초기화 (채널 삭제 시)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                await db.execute('''
                    UPDATE battle_tag_log_settings
                    SET log_channel_id = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                ''', (guild_id,))
                
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 로그 채널 초기화 실패: {e}")
            return False

    async def get_all_registered_users(self, guild_id: str) -> List[Dict]:
        """서버의 모든 등록된 유저 조회 (대표 배틀태그 포함)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        r.user_id, 
                        r.username, 
                        COALESCE(ubt.battle_tag, r.battle_tag) as battle_tag,  -- 🔥 핵심!
                        r.main_position, 
                        r.current_season_tier, 
                        r.birth_year
                    FROM registered_users r
                    LEFT JOIN user_battle_tags ubt 
                        ON r.guild_id = ubt.guild_id 
                        AND r.user_id = ubt.user_id 
                        AND ubt.is_primary = TRUE
                    WHERE r.guild_id = ? AND r.is_active = TRUE
                    ORDER BY r.username
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return [{
                        'user_id': row[0], 
                        'username': row[1],
                        'battle_tag': row[2],
                        'main_position': row[3],
                        'current_season_tier': row[4],
                        'birth_year': row[5]
                    } for row in rows]
        except Exception as e:
            print(f"❌ 등록 유저 조회 실패: {e}")
            return []

    async def record_scrim_result(
        self, 
        guild_id: str, 
        user_id: str, 
        position: str, 
        result: str,
        map_type: Optional[str] = None,
        map_name: Optional[str] = None
    ) -> None:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 포지션 매핑
                position_map = {
                    '탱커': 'tank',
                    '딜러': 'dps', 
                    '힐러': 'support'
                }
                
                position_key = position_map.get(position)
                
                if not position_key:
                    print(f"⚠️ 알 수 없는 포지션: {position}, 기본값 'dps' 사용")
                    position_key = 'dps'
                
                # 승리 여부
                is_win = 1 if result == 'win' else 0
                
                # 기존 통계 조회
                async with db.execute('''
                    SELECT total_games, total_wins,
                        tank_games, tank_wins,
                        dps_games, dps_wins,
                        support_games, support_wins
                    FROM user_statistics
                    WHERE user_id = ? AND guild_id = ?
                ''', (user_id, guild_id)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # 기존 데이터 업데이트
                    total_games = existing[0] + 1
                    total_wins = existing[1] + is_win
                    tank_games = existing[2] + (1 if position_key == 'tank' else 0)
                    tank_wins = existing[3] + (is_win if position_key == 'tank' else 0)
                    dps_games = existing[4] + (1 if position_key == 'dps' else 0)
                    dps_wins = existing[5] + (is_win if position_key == 'dps' else 0)
                    support_games = existing[6] + (1 if position_key == 'support' else 0)
                    support_wins = existing[7] + (is_win if position_key == 'support' else 0)
                    
                    await db.execute('''
                        UPDATE user_statistics
                        SET total_games = ?,
                            total_wins = ?,
                            tank_games = ?,
                            tank_wins = ?,
                            dps_games = ?,
                            dps_wins = ?,
                            support_games = ?,
                            support_wins = ?,
                            last_updated = ?
                        WHERE user_id = ? AND guild_id = ?
                    ''', (
                        total_games, total_wins,
                        tank_games, tank_wins,
                        dps_games, dps_wins,
                        support_games, support_wins,
                        datetime.now().isoformat(),
                        user_id, guild_id
                    ))
                else:
                    # 새 레코드 생성
                    total_games = 1
                    total_wins = is_win
                    tank_games = 1 if position_key == 'tank' else 0
                    tank_wins = is_win if position_key == 'tank' else 0
                    dps_games = 1 if position_key == 'dps' else 0
                    dps_wins = is_win if position_key == 'dps' else 0
                    support_games = 1 if position_key == 'support' else 0
                    support_wins = is_win if position_key == 'support' else 0
                    
                    await db.execute('''
                        INSERT INTO user_statistics (
                            user_id, guild_id,
                            total_games, total_wins,
                            tank_games, tank_wins,
                            dps_games, dps_wins,
                            support_games, support_wins,
                            last_updated
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id, guild_id,
                        total_games, total_wins,
                        tank_games, tank_wins,
                        dps_games, dps_wins,
                        support_games, support_wins,
                        datetime.now().isoformat()
                    ))
                
                await db.commit()
                
                # 로그 출력
                result_text = "승리" if is_win else "패배"
                print(f"✅ 통계 업데이트: User {user_id} - {position}({position_key}) {result_text}")
                
        except Exception as e:
            print(f"❌ record_scrim_result 실패: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def get_user_statistics(self, guild_id: str, user_id: str) -> Optional[Dict]:
        """특정 유저의 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT total_games, total_wins,
                        tank_games, tank_wins,
                        dps_games, dps_wins,
                        support_games, support_wins
                    FROM user_statistics
                    WHERE user_id = ? AND guild_id = ?
                ''', (user_id, guild_id)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result:
                        return {
                            'total_games': result[0],
                            'total_wins': result[1],
                            'tank_games': result[2],
                            'tank_wins': result[3],
                            'dps_games': result[4],
                            'dps_wins': result[5],
                            'support_games': result[6],
                            'support_wins': result[7]
                        }
                    
                    return None
                    
        except Exception as e:
            print(f"❌ 유저 통계 조회 실패: {e}")
            return None

    async def set_voice_monitor_enabled(self, guild_id: str, enabled: bool) -> bool:
        """음성 모니터링 활성화 설정"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('''
                    INSERT INTO voice_monitor_settings (guild_id, enabled, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id) 
                    DO UPDATE SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, enabled, enabled))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 음성 모니터링 설정 저장 실패: {e}")
            return False

    async def is_voice_monitor_enabled(self, guild_id: str) -> bool:
        """음성 모니터링 활성화 여부 확인"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT enabled FROM voice_monitor_settings
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else False
        except Exception as e:
            print(f"❌ 음성 모니터링 설정 조회 실패: {e}")
            return False

    async def update_session_screen_share_status(self, session_uuid: str, is_screen_sharing: bool):
        """
        세션 화면 공유 상태 업데이트 (음소거와 동일한 패턴)
        
        Args:
            session_uuid: 세션 UUID
            is_screen_sharing: 새로운 화면 공유 상태
        """
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 현재 세션 정보 조회
            cursor = await db.execute('''
                SELECT is_screen_sharing, updated_at, screen_share_seconds 
                FROM voice_sessions 
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            row = await cursor.fetchone()
            
            if not row:
                return
            
            old_screen_sharing = bool(row[0])
            last_update = datetime.fromisoformat(row[1])
            current_screen_share_seconds = row[2] if row[2] else 0
            
            now = datetime.utcnow()
            elapsed = (now - last_update).total_seconds()
            
            # 화면 공유 시간 계산
            new_screen_share_seconds = current_screen_share_seconds
            if old_screen_sharing:
                # 이전에 화면 공유 중이었으면 경과 시간을 추가
                new_screen_share_seconds += elapsed
            
            # 업데이트
            await db.execute('''
                UPDATE voice_sessions 
                SET is_screen_sharing = ?, updated_at = ?, screen_share_seconds = ?
                WHERE session_uuid = ?
            ''', (is_screen_sharing, now.isoformat(), new_screen_share_seconds, session_uuid))
            await db.commit()

    async def end_voice_session_with_screen_share(self, session_uuid: str):
        """
        음성 세션 종료 (음소거 + 화면 공유 시간 반영)
        
        Returns:
            (total_duration, active_duration, screen_share_duration): 전체, 활성, 화면공유 시간 (초)
        """
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 세션 정보 조회
            cursor = await db.execute('''
                SELECT join_time, is_muted, is_screen_sharing, updated_at, 
                    muted_seconds, screen_share_seconds 
                FROM voice_sessions 
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            row = await cursor.fetchone()
            
            if not row:
                return 0, 0, 0
            
            join_time = datetime.fromisoformat(row[0])
            is_muted = bool(row[1])
            is_screen_sharing = bool(row[2])
            last_update = datetime.fromisoformat(row[3])
            muted_seconds = row[4] if row[4] else 0
            screen_share_seconds = row[5] if row[5] else 0
            
            leave_time = datetime.utcnow()
            
            # 전체 체류 시간
            total_duration = int((leave_time - join_time).total_seconds())
            
            # 마지막 구간 처리
            last_elapsed = (leave_time - last_update).total_seconds()
            if is_muted:
                muted_seconds += last_elapsed
            if is_screen_sharing:
                screen_share_seconds += last_elapsed
            
            # 활성 시간 = 전체 시간 - 음소거 시간
            active_duration = int(total_duration - muted_seconds)
            active_duration = max(0, active_duration)  # 음수 방지
            
            # 화면 공유 시간
            screen_share_duration = int(screen_share_seconds)
            
            # 세션 종료
            await db.execute('''
                UPDATE voice_sessions 
                SET is_active = FALSE, 
                    leave_time = ?, 
                    duration_seconds = ?,
                    muted_seconds = ?,
                    screen_share_seconds = ?,
                    updated_at = ?
                WHERE session_uuid = ?
            ''', (leave_time.isoformat(), total_duration, int(muted_seconds), 
                screen_share_duration, leave_time.isoformat(), session_uuid))
            await db.commit()
            
            return total_duration, active_duration, screen_share_duration

    async def create_voice_session(
        self, 
        guild_id: str, 
        user_id: str, 
        channel_id: str, 
        is_muted: bool = False,
        is_screen_sharing: bool = False
    ):
        """새 음성 세션 생성"""
        import uuid
        from datetime import datetime
        
        session_uuid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO voice_sessions (
                    session_uuid, guild_id, user_id, channel_id, 
                    join_time, is_muted, is_screen_sharing, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session_uuid, guild_id, user_id, channel_id, 
                now, is_muted, is_screen_sharing, now))
            
            await db.commit()
        
        return session_uuid


    async def end_voice_session(self, session_uuid: str):
        """음성 세션 종료"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 세션 정보 조회
            cursor = await db.execute('''
                SELECT join_time FROM voice_sessions WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            row = await cursor.fetchone()
            
            if row:
                join_time = datetime.fromisoformat(row[0])
                leave_time = datetime.utcnow()
                duration = int((leave_time - join_time).total_seconds())
                
                await db.execute('''
                    UPDATE voice_sessions 
                    SET is_active = FALSE, leave_time = ?, duration_seconds = ?, updated_at = ?
                    WHERE session_uuid = ?
                ''', (leave_time.isoformat(), duration, datetime.utcnow().isoformat(), session_uuid))
                await db.commit()
                
                return duration
        
        return 0

    async def update_user_screen_share_time(
        self, 
        guild_id: str, 
        user_id: str, 
        screen_share_seconds: int
    ):
        """유저의 총 화면 공유 시간 업데이트"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE user_levels
                SET total_screen_share_seconds = total_screen_share_seconds + ?,
                    updated_at = datetime('now')
                WHERE guild_id = ? AND user_id = ?
            ''', (screen_share_seconds, guild_id, user_id))
            
            await db.commit()


    async def set_screen_share_bonus_settings(
        self,
        guild_id: str,
        enabled: bool,
        multiplier: float
    ):
        """화면 공유 보너스 설정"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO voice_level_settings (
                    guild_id, screen_share_bonus_enabled, screen_share_multiplier, updated_at
                )
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(guild_id) DO UPDATE SET
                    screen_share_bonus_enabled = ?,
                    screen_share_multiplier = ?,
                    updated_at = datetime('now')
            ''', (guild_id, enabled, multiplier, enabled, multiplier))
            
            await db.commit()


    async def get_active_session(self, guild_id: str, user_id: str):
        """유저의 활성 세션 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT session_uuid, channel_id, join_time, is_muted
                FROM voice_sessions
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ORDER BY join_time DESC
                LIMIT 1
            ''', (guild_id, user_id))
            row = await cursor.fetchone()
            
            if row:
                return {
                    'session_uuid': row[0],
                    'channel_id': row[1],
                    'join_time': row[2],
                    'is_muted': bool(row[3])
                }
        return None


    async def update_session_mute_status(self, session_uuid: str, is_muted: bool):
        """세션 음소거 상태 업데이트"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE voice_sessions 
                SET is_muted = ?, updated_at = ?
                WHERE session_uuid = ?
            ''', (is_muted, datetime.utcnow().isoformat(), session_uuid))
            await db.commit()


    async def get_users_in_channel(self, guild_id: str, channel_id: str):
        """특정 음성 채널에 있는 활성 유저 목록"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT user_id, session_uuid, is_muted
                FROM voice_sessions
                WHERE guild_id = ? AND channel_id = ? AND is_active = TRUE
            ''', (guild_id, channel_id))
            rows = await cursor.fetchall()
            
            return [{'user_id': row[0], 'session_uuid': row[1], 'is_muted': bool(row[2])} for row in rows]

    async def update_relationship_time(self, guild_id: str, user1_id: str, user2_id: str, seconds: int):
        """두 유저 간 함께한 시간 업데이트"""
        from datetime import datetime

        cursor = await db.execute('''
            SELECT COUNT(*) FROM user_levels 
            WHERE guild_id = ? AND user_id IN (?, ?)
        ''', (guild_id, user1_id, user2_id))
        
        count = (await cursor.fetchone())[0]
        
        if count != 2:
            # 한쪽이라도 user_levels에 없으면 관계 업데이트 안 함
            return
        
        # user1_id가 항상 작도록 정렬 (UNIQUE 제약 조건)
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        async with aiosqlite.connect(self.db_path) as db:
            # 기존 관계 조회
            cursor = await db.execute('''
                SELECT total_time_seconds FROM user_relationships
                WHERE guild_id = ? AND user1_id = ? AND user2_id = ?
            ''', (guild_id, user1_id, user2_id))
            row = await cursor.fetchone()
            
            now = datetime.utcnow().isoformat()
            
            if row:
                # 기존 관계 업데이트
                new_total = row[0] + seconds
                await db.execute('''
                    UPDATE user_relationships
                    SET total_time_seconds = ?, last_played_together = ?, updated_at = ?
                    WHERE guild_id = ? AND user1_id = ? AND user2_id = ?
                ''', (new_total, now, now, guild_id, user1_id, user2_id))
            else:
                # 새 관계 생성
                await db.execute('''
                    INSERT INTO user_relationships 
                    (guild_id, user1_id, user2_id, total_time_seconds, last_played_together)
                    VALUES (?, ?, ?, ?, ?)
                ''', (guild_id, user1_id, user2_id, seconds, now))
            
            await db.commit()

    async def get_relationship(self, guild_id: str, user1_id: str, user2_id: str):
        """두 유저 간 관계 정보 조회"""
        # user1_id가 항상 작도록 정렬
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT total_time_seconds, last_played_together, relationship_multiplier
                FROM user_relationships
                WHERE guild_id = ? AND user1_id = ? AND user2_id = ?
            ''', (guild_id, user1_id, user2_id))
            row = await cursor.fetchone()
            
            if row:
                return {
                    'total_time_seconds': row[0],
                    'last_played_together': row[1],
                    'relationship_multiplier': row[2]
                }
        return None

    async def get_user_relationships(self, guild_id: str, user_id: str):
        """특정 유저의 모든 관계 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT 
                    CASE WHEN user1_id = ? THEN user2_id ELSE user1_id END as partner_id,
                    total_time_seconds,
                    last_played_together
                FROM user_relationships
                WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?)
                ORDER BY total_time_seconds DESC
            ''', (user_id, guild_id, user_id, user_id))
            rows = await cursor.fetchall()
            
            return [{'partner_id': row[0], 'total_time_seconds': row[1], 'last_played_together': row[2]} 
                    for row in rows]

    async def get_voice_level_settings(self, guild_id: str):
        """서버 음성 레벨 설정 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT enabled, notification_channel_id, base_exp_per_minute, 
                    daily_exp_limit, min_session_minutes, check_mute_status,
                    screen_share_bonus_enabled, screen_share_multiplier
                FROM voice_level_settings
                WHERE guild_id = ?
            ''', (guild_id,))
            row = await cursor.fetchone()
            
            if row:
                return {
                    'enabled': bool(row[0]),
                    'notification_channel_id': row[1],
                    'base_exp_per_minute': row[2],
                    'daily_exp_limit': row[3],
                    'min_session_minutes': row[4],
                    'check_mute_status': bool(row[5]),
                    'screen_share_bonus_enabled': bool(row[6]) if row[6] is not None else True,
                    'screen_share_multiplier': row[7] if row[7] is not None else 1.5
                }
            else:
                return {
                    'enabled': False,
                    'notification_channel_id': None,
                    'base_exp_per_minute': 10.0,
                    'daily_exp_limit': 5000,
                    'min_session_minutes': 30,
                    'check_mute_status': True,
                    'screen_share_bonus_enabled': True,
                    'screen_share_multiplier': 1.5
                }

    async def set_voice_level_enabled(self, guild_id: str, enabled: bool):
        """음성 레벨 기능 활성화/비활성화"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO voice_level_settings (guild_id, enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET enabled = ?, updated_at = ?
            ''', (guild_id, enabled, datetime.utcnow().isoformat(), enabled, datetime.utcnow().isoformat()))
            await db.commit()

    async def get_user_level(self, guild_id: str, user_id: str):
        """유저 레벨 정보 조회 (화면 공유 시간 포함)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT id, guild_id, user_id, current_level, current_exp, total_exp,
                    total_play_time_seconds, total_screen_share_seconds, unique_partners_count, 
                    last_exp_gain, daily_exp_gained, last_daily_reset, created_at, updated_at
                FROM user_levels
                WHERE guild_id = ? AND user_id = ?
            ''', (guild_id, user_id))
            row = await cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'guild_id': row[1],
                    'user_id': row[2],
                    'current_level': row[3],
                    'current_exp': row[4],
                    'total_exp': row[5],
                    'total_play_time_seconds': row[6],
                    'total_screen_share_seconds': row[7] if row[7] is not None else 0,
                    'unique_partners_count': row[8],
                    'last_exp_gain': row[9],
                    'daily_exp_gained': row[10],
                    'last_daily_reset': row[11],
                    'created_at': row[12],
                    'updated_at': row[13]
                }
        return None


    async def create_user_level(self, guild_id: str, user_id: str):
        """새로운 유저 레벨 레코드 생성"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow().isoformat()
            await db.execute('''
                INSERT INTO user_levels 
                (guild_id, user_id, current_level, current_exp, total_exp, 
                total_play_time_seconds, unique_partners_count, last_daily_reset)
                VALUES (?, ?, 0, 0, 0, 0, 0, ?)
            ''', (guild_id, user_id, now))
            await db.commit()


    async def update_user_level(
        self,
        guild_id: str,
        user_id: str,
        current_level: int,
        current_exp: int,
        total_exp: int,
        daily_exp_gained: int
    ):
        """유저 레벨 정보 업데이트"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow().isoformat()
            await db.execute('''
                UPDATE user_levels
                SET current_level = ?, current_exp = ?, total_exp = ?,
                    daily_exp_gained = ?, last_exp_gain = ?, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (current_level, current_exp, total_exp, daily_exp_gained, 
                now, now, guild_id, user_id))
            await db.commit()


    async def update_user_play_time(self, guild_id: str, user_id: str, seconds_to_add: int):
        """유저 총 플레이 시간 업데이트"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE user_levels
                SET total_play_time_seconds = total_play_time_seconds + ?,
                    updated_at = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (seconds_to_add, datetime.utcnow().isoformat(), guild_id, user_id))
            await db.commit()


    async def update_unique_partners_count(self, guild_id: str, user_id: str):
        """유저의 고유 파트너 수 업데이트 (캐싱용)"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 현재 관계 수 계산
            cursor = await db.execute('''
                SELECT COUNT(*) FROM user_relationships
                WHERE guild_id = ? AND (user1_id = ? OR user2_id = ?)
            ''', (guild_id, user_id, user_id))
            count = (await cursor.fetchone())[0]
            
            # 업데이트
            await db.execute('''
                UPDATE user_levels
                SET unique_partners_count = ?, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (count, datetime.utcnow().isoformat(), guild_id, user_id))
            await db.commit()


    async def reset_daily_exp(self, guild_id: str, user_id: str):
        """일일 exp 리셋"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            now = datetime.utcnow().isoformat()
            await db.execute('''
                UPDATE user_levels
                SET daily_exp_gained = 0, last_daily_reset = ?, updated_at = ?
                WHERE guild_id = ? AND user_id = ?
            ''', (now, now, guild_id, user_id))
            await db.commit()


    async def get_level_leaderboard(self, guild_id: str, limit: int = 10):
        """레벨 순위표 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT user_id, current_level, total_exp, total_play_time_seconds, unique_partners_count
                FROM user_levels
                WHERE guild_id = ?
                ORDER BY current_level DESC, total_exp DESC
                LIMIT ?
            ''', (guild_id, limit))
            rows = await cursor.fetchall()
            
            return [
                {
                    'user_id': row[0],
                    'current_level': row[1],
                    'total_exp': row[2],
                    'total_play_time_seconds': row[3],
                    'unique_partners_count': row[4]
                }
                for row in rows
            ]


    async def get_diversity_leaderboard(self, guild_id: str, limit: int = 10):
        """다양성 순위표 조회 (많은 사람과 플레이한 순)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT user_id, unique_partners_count, current_level, total_exp
                FROM user_levels
                WHERE guild_id = ? AND unique_partners_count > 0
                ORDER BY unique_partners_count DESC, total_exp DESC
                LIMIT ?
            ''', (guild_id, limit))
            rows = await cursor.fetchall()
            
            return [
                {
                    'user_id': row[0],
                    'unique_partners_count': row[1],
                    'current_level': row[2],
                    'total_exp': row[3]
                }
                for row in rows
            ]


    async def get_user_rank(self, guild_id: str, user_id: str):
        """유저의 서버 내 순위 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            # 레벨 순위
            cursor = await db.execute('''
                SELECT COUNT(*) + 1 as rank
                FROM user_levels
                WHERE guild_id = ? 
                AND (current_level > (SELECT current_level FROM user_levels WHERE guild_id = ? AND user_id = ?)
                    OR (current_level = (SELECT current_level FROM user_levels WHERE guild_id = ? AND user_id = ?)
                        AND total_exp > (SELECT total_exp FROM user_levels WHERE guild_id = ? AND user_id = ?)))
            ''', (guild_id, guild_id, user_id, guild_id, user_id, guild_id, user_id))
            level_rank = (await cursor.fetchone())[0]
            
            # 다양성 순위
            cursor = await db.execute('''
                SELECT COUNT(*) + 1 as rank
                FROM user_levels
                WHERE guild_id = ? 
                AND unique_partners_count > (SELECT unique_partners_count FROM user_levels WHERE guild_id = ? AND user_id = ?)
            ''', (guild_id, guild_id, user_id))
            diversity_rank = (await cursor.fetchone())[0]
            
            # 총 유저 수
            cursor = await db.execute('''
                SELECT COUNT(*) FROM user_levels WHERE guild_id = ?
            ''', (guild_id,))
            total_users = (await cursor.fetchone())[0]
            
            return {
                'level_rank': level_rank,
                'diversity_rank': diversity_rank,
                'total_users': total_users
            }


    async def get_top_relationships(self, guild_id: str, limit: int = 10):
        """가장 많은 시간을 함께한 관계 순위"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT user1_id, user2_id, total_time_seconds, last_played_together
                FROM user_relationships
                WHERE guild_id = ?
                ORDER BY total_time_seconds DESC
                LIMIT ?
            ''', (guild_id, limit))
            rows = await cursor.fetchall()
            
            return [
                {
                    'user1_id': row[0],
                    'user2_id': row[1],
                    'total_time_seconds': row[2],
                    'last_played_together': row[3]
                }
                for row in rows
            ]

    async def set_notification_channel(self, guild_id: str, channel_id: str):
        """알림 채널 설정"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO voice_level_settings (guild_id, notification_channel_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET 
                    notification_channel_id = ?, 
                    updated_at = ?
            ''', (guild_id, channel_id, datetime.utcnow().isoformat(), 
                channel_id, datetime.utcnow().isoformat()))
            await db.commit()


    async def clear_notification_channel(self, guild_id: str):
        """알림 채널 제거"""
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE voice_level_settings
                SET notification_channel_id = NULL, updated_at = ?
                WHERE guild_id = ?
            ''', (datetime.utcnow().isoformat(), guild_id))
            await db.commit()


    async def update_voice_level_setting(self, guild_id: str, setting_name: str, value):
        """개별 설정 업데이트 (범용)"""
        from datetime import datetime
        
        # 허용된 설정 이름 체크
        allowed_settings = [
            'base_exp_per_minute',
            'daily_exp_limit',
            'min_session_minutes',
            'check_mute_status'
        ]
        
        if setting_name not in allowed_settings:
            raise ValueError(f"Invalid setting name: {setting_name}")
        
        async with aiosqlite.connect(self.db_path) as db:
            # 기존 설정이 없으면 생성
            cursor = await db.execute('''
                SELECT guild_id FROM voice_level_settings WHERE guild_id = ?
            ''', (guild_id,))
            
            if not await cursor.fetchone():
                await db.execute('''
                    INSERT INTO voice_level_settings (guild_id) VALUES (?)
                ''', (guild_id,))
            
            # 설정 업데이트
            query = f'''
                UPDATE voice_level_settings
                SET {setting_name} = ?, updated_at = ?
                WHERE guild_id = ?
            '''
            await db.execute(query, (value, datetime.utcnow().isoformat(), guild_id))
            await db.commit()

    async def update_session_mute_status_with_time(self, session_uuid: str, is_muted: bool):
        """
        세션 음소거 상태 업데이트 및 음소거 시간 계산
        
        Args:
            session_uuid: 세션 UUID
            is_muted: 새로운 음소거 상태
        """
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 현재 세션 정보 조회
            cursor = await db.execute('''
                SELECT is_muted, updated_at, muted_seconds 
                FROM voice_sessions 
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            row = await cursor.fetchone()
            
            if not row:
                return
            
            old_muted = bool(row[0])
            last_update = datetime.fromisoformat(row[1])
            current_muted_seconds = row[2] if row[2] else 0
            
            now = datetime.utcnow()
            elapsed = (now - last_update).total_seconds()
            
            # 음소거 시간 계산
            new_muted_seconds = current_muted_seconds
            if old_muted:
                # 이전에 음소거 상태였으면 경과 시간을 음소거 시간에 추가
                new_muted_seconds += elapsed
            
            # 업데이트
            await db.execute('''
                UPDATE voice_sessions 
                SET is_muted = ?, updated_at = ?, muted_seconds = ?
                WHERE session_uuid = ?
            ''', (is_muted, now.isoformat(), new_muted_seconds, session_uuid))
            await db.commit()


    async def end_voice_session_with_mute(self, session_uuid: str):
        """
        음성 세션 종료 (음소거 시간 반영)
        
        Returns:
            (total_duration, active_duration): 전체 시간, 활성 시간 (초)
        """
        from datetime import datetime
        
        async with aiosqlite.connect(self.db_path) as db:
            # 세션 정보 조회
            cursor = await db.execute('''
                SELECT join_time, is_muted, updated_at, muted_seconds 
                FROM voice_sessions 
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            row = await cursor.fetchone()
            
            if not row:
                return 0, 0
            
            join_time = datetime.fromisoformat(row[0])
            is_muted = bool(row[1])
            last_update = datetime.fromisoformat(row[2])
            muted_seconds = row[3] if row[3] else 0
            
            leave_time = datetime.utcnow()
            
            # 전체 체류 시간
            total_duration = int((leave_time - join_time).total_seconds())
            
            # 마지막 구간 음소거 시간 추가
            last_elapsed = (leave_time - last_update).total_seconds()
            if is_muted:
                muted_seconds += last_elapsed
            
            # 활성 시간 = 전체 시간 - 음소거 시간
            active_duration = int(total_duration - muted_seconds)
            active_duration = max(0, active_duration)  # 음수 방지
            
            # 세션 종료
            await db.execute('''
                UPDATE voice_sessions 
                SET is_active = FALSE, 
                    leave_time = ?, 
                    duration_seconds = ?,
                    muted_seconds = ?,
                    updated_at = ?
                WHERE session_uuid = ?
            ''', (leave_time.isoformat(), total_duration, int(muted_seconds), 
                leave_time.isoformat(), session_uuid))
            await db.commit()
            
            return total_duration, active_duration

    async def mark_session_as_solo(self, session_uuid: str):
        """세션을 혼자 있는 상태로 표시"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE voice_sessions 
                SET is_solo = TRUE,
                    last_solo_marked_at = CURRENT_TIMESTAMP
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            await db.commit()

    async def mark_session_as_active_with_partners(self, session_uuid: str):
        """세션을 파트너와 함께 있는 상태로 표시"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE voice_sessions 
                SET is_solo = FALSE
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            await db.commit()

    async def get_session_elapsed_seconds(self, session_uuid: str) -> int:
        """세션의 경과 시간 계산 (초)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT join_time, muted_seconds
                FROM voice_sessions
                WHERE session_uuid = ? AND is_active = TRUE
            ''', (session_uuid,))
            
            row = await cursor.fetchone()
            if not row:
                return 0
            
            join_time_str = row[0]
            muted_seconds = row[1] or 0
            
            # join_time을 datetime으로 변환
            from datetime import datetime
            join_time = datetime.fromisoformat(join_time_str)
            
            # 총 경과 시간 - 음소거 시간
            total_elapsed = (datetime.now() - join_time).total_seconds()
            active_seconds = total_elapsed - muted_seconds
            
            return int(max(0, active_seconds))

    async def batch_update_relationships(self, updates: list):
        """관계 시간 배치 업데이트
        
        Args:
            updates: [(guild_id, user1_id, user2_id, seconds_to_add), ...]
        """
        async with aiosqlite.connect(self.db_path) as db:
            for guild_id, user1_id, user2_id, seconds in updates:
                # user1_id가 항상 작도록 정렬
                if user1_id > user2_id:
                    user1_id, user2_id = user2_id, user1_id
                
                await db.execute('''
                    INSERT INTO user_relationships (
                        guild_id, user1_id, user2_id, 
                        total_time_seconds, last_played_together
                    )
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, user1_id, user2_id) 
                    DO UPDATE SET
                        total_time_seconds = total_time_seconds + ?,
                        last_played_together = CURRENT_TIMESTAMP
                ''', (guild_id, user1_id, user2_id, seconds, seconds))
            
            await db.commit()

    async def get_relationships_for_pairs(self, guild_id: str, pairs: list) -> dict:
        """여러 페어의 관계 정보 한 번에 조회
        
        Args:
            pairs: [(user1_id, user2_id), ...]
            
        Returns:
            {(user1_id, user2_id): {'total_time_seconds': ..., ...}, ...}
        """
        if not pairs:
            return {}
        
        results = {}
        
        async with aiosqlite.connect(self.db_path) as db:
            # IN 절을 사용한 배치 조회
            placeholders = ','.join(['(?,?)' for _ in pairs])
            params = [guild_id]
            for user1, user2 in pairs:
                if user1 > user2:
                    user1, user2 = user2, user1
                params.extend([user1, user2])
            
            cursor = await db.execute(f'''
                SELECT user1_id, user2_id, total_time_seconds, last_played_together
                FROM user_relationships
                WHERE guild_id = ? 
                AND (user1_id, user2_id) IN ({placeholders})
            ''', params)
            
            rows = await cursor.fetchall()
            
            for row in rows:
                key = (row[0], row[1])
                results[key] = {
                    'user1_id': row[0],
                    'user2_id': row[1],
                    'total_time_seconds': row[2],
                    'last_played_together': row[3]
                }
        
        return results

    async def get_members_never_played_with(self, guild_id: str, user_id: str, limit: int = 3):
        """
        함께 한 번도 플레이하지 않은 멤버 조회
        
        Args:
            guild_id: 서버 ID
            user_id: 유저 ID
            limit: 반환할 최대 인원
            
        Returns:
            List[str]: 함께 안 한 유저 ID 리스트
        """
        async with aiosqlite.connect(self.db_path) as db:
            # 1. 해당 유저와 관계가 있는 모든 유저 ID 조회
            cursor = await db.execute('''
                SELECT DISTINCT
                    CASE 
                        WHEN user1_id = ? THEN user2_id
                        ELSE user1_id
                    END as partner_id
                FROM user_relationships
                WHERE guild_id = ? 
                AND (user1_id = ? OR user2_id = ?)
            ''', (user_id, guild_id, user_id, user_id))
            
            played_with = [row[0] for row in await cursor.fetchall()]
            
            # 2. 해당 서버의 모든 레벨 유저 조회 (본인 제외)
            cursor = await db.execute('''
                SELECT user_id
                FROM user_levels
                WHERE guild_id = ? AND user_id != ?
                ORDER BY RANDOM()
                LIMIT ?
            ''', (guild_id, user_id, limit * 3))  # 여유있게 조회
            
            all_users = [row[0] for row in await cursor.fetchall()]
            
            # 3. 함께 안 한 사람만 필터링
            never_played = [uid for uid in all_users if uid not in played_with]
            
            return never_played[:limit]

    async def get_members_never_played_with_priority(
        self, 
        guild_id: str, 
        user_id: str, 
        online_user_ids: List[str] = None,
        limit: int = 3
    ):
        async with aiosqlite.connect(self.db_path) as db:
            # 1. 함께 플레이한 적 있는 유저들
            cursor = await db.execute('''
                SELECT DISTINCT
                    CASE 
                        WHEN user1_id = ? THEN user2_id
                        ELSE user1_id
                    END as partner_id
                FROM user_relationships
                WHERE guild_id = ? 
                AND (user1_id = ? OR user2_id = ?)
            ''', (user_id, guild_id, user_id, user_id))
            
            played_with = set(row[0] for row in await cursor.fetchall())
            
            # 2. 해당 서버의 모든 유저 조회 (본인 제외)
            cursor = await db.execute('''
                SELECT user_id
                FROM user_levels
                WHERE guild_id = ? AND user_id != ?
            ''', (guild_id, user_id))
            
            all_users = [row[0] for row in await cursor.fetchall()]
            
            # 3. 함께 안 한 사람 필터링
            never_played = [uid for uid in all_users if uid not in played_with]
            
            # 4. 온라인/오프라인 분류
            online_set = set(online_user_ids) if online_user_ids else set()
            
            online_never = [uid for uid in never_played if uid in online_set]
            offline_never = [uid for uid in never_played if uid not in online_set]
            
            # 5. 온라인 우선 + 랜덤 섞기
            import random
            random.shuffle(online_never)
            random.shuffle(offline_never)
            
            # 6. 결과 조합 (온라인 우선)
            result = []
            for uid in online_never[:limit]:
                result.append({'user_id': uid, 'is_online': True})
            
            remaining = limit - len(result)
            for uid in offline_never[:remaining]:
                result.append({'user_id': uid, 'is_online': False})
            
            return result


    async def get_dormant_relationships(
        self, 
        guild_id: str, 
        user_id: str,
        min_hours: float = 1.0,
        days_threshold: int = 7,
        limit: int = 3
    ):
        from datetime import datetime, timedelta
        
        async with aiosqlite.connect(self.db_path) as db:
            # 기준 시간 (N일 전)
            threshold_date = datetime.utcnow() - timedelta(days=days_threshold)
            threshold_str = threshold_date.isoformat()
            
            min_seconds = int(min_hours * 3600)
            
            # 조건:
            # 1. 최소 min_hours 이상 함께 플레이
            # 2. 마지막 플레이가 days_threshold일 이전
            cursor = await db.execute('''
                SELECT 
                    CASE 
                        WHEN user1_id = ? THEN user2_id
                        ELSE user1_id
                    END as partner_id,
                    total_time_seconds,
                    last_played_together
                FROM user_relationships
                WHERE guild_id = ?
                AND (user1_id = ? OR user2_id = ?)
                AND total_time_seconds >= ?
                AND last_played_together IS NOT NULL
                AND last_played_together < ?
                ORDER BY last_played_together ASC
                LIMIT ?
            ''', (user_id, guild_id, user_id, user_id, min_seconds, threshold_str, limit))
            
            rows = await cursor.fetchall()
            
            result = []
            for row in rows:
                partner_id = row[0]
                total_seconds = row[1]
                last_played = row[2]
                
                total_hours = total_seconds / 3600.0
                
                # 며칠 전인지 계산
                if last_played:
                    last_date = datetime.fromisoformat(last_played)
                    days_ago = (datetime.utcnow() - last_date).days
                else:
                    days_ago = 999
                
                result.append({
                    'partner_id': partner_id,
                    'total_hours': total_hours,
                    'total_seconds': total_seconds,
                    'days_ago': days_ago,
                    'last_played': last_played
                })
            
            return result

    async def add_session_partners(self, session_uuid: str, partner_ids: List[str]):
        """
        세션에 여러 파트너 추가 (입장 시점에 이미 채널에 있던 사람들)
        
        Args:
            session_uuid: 세션 UUID
            partner_ids: 파트너 ID 리스트
        """
        if not partner_ids:
            return
        
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            for partner_id in partner_ids:
                await db.execute('''
                    INSERT OR IGNORE INTO session_partners 
                    (session_uuid, partner_id, joined_together_at)
                    VALUES (?, ?, ?)
                ''', (session_uuid, partner_id, now))
            await db.commit()


    async def add_session_partner(self, session_uuid: str, partner_id: str):
        """
        세션에 파트너 1명 추가 (중간에 입장한 사람)
        
        Args:
            session_uuid: 세션 UUID
            partner_id: 파트너 ID
        """
        from datetime import datetime
        now = datetime.utcnow().isoformat()
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO session_partners 
                (session_uuid, partner_id, joined_together_at)
                VALUES (?, ?, ?)
            ''', (session_uuid, partner_id, now))
            await db.commit()


    async def get_session_partners(self, session_uuid: str) -> List[str]:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT DISTINCT partner_id 
                FROM session_partners
                WHERE session_uuid = ?
            ''', (session_uuid,))
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def update_user_main_position(self, guild_id: str, user_id: str, main_position: str) -> bool:
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            try:
                await db.execute('''
                    UPDATE registered_users 
                    SET main_position = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ? AND user_id = ? AND (main_position IS NULL OR main_position = '')
                ''', (main_position, guild_id, user_id))
                
                await db.commit()
                return True
            except Exception as e:
                print(f"주 포지션 업데이트 오류: {e}")
                return False

    async def update_user_profile_selective(self, guild_id: str, user_id: str, update_data: Dict) -> bool:
        """선택적 사용자 프로필 업데이트"""
        if not update_data:
            return True
        
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            try:
                # 동적으로 UPDATE 쿼리 생성
                set_clauses = []
                values = []
                
                for field, value in update_data.items():
                    set_clauses.append(f"{field} = ?")
                    values.append(value)
                
                set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                values.extend([guild_id, user_id])
                
                query = f'''
                    UPDATE registered_users 
                    SET {', '.join(set_clauses)}
                    WHERE guild_id = ? AND user_id = ?
                '''
                
                await db.execute(query, values)
                await db.commit()
                return True
            except Exception as e:
                print(f"선택적 프로필 업데이트 오류: {e}")
                return False

    async def set_inquiry_channel(self, guild_id: str, channel_id: str) -> bool:
        """관리팀 문의 채널 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 기존 설정이 있는지 확인
                async with db.execute('''
                    SELECT guild_id FROM inquiry_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    exists = await cursor.fetchone()
                
                if exists:
                    # 업데이트
                    await db.execute('''
                        UPDATE inquiry_settings 
                        SET team_inquiry_channel_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (channel_id, guild_id))
                else:
                    # 새로 생성
                    await db.execute('''
                        INSERT INTO inquiry_settings (guild_id, team_inquiry_channel_id)
                        VALUES (?, ?)
                    ''', (guild_id, channel_id))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 문의 채널 설정 실패: {e}")
            return False

    async def get_inquiry_channel(self, guild_id: str) -> Optional[str]:
        """관리팀 문의 채널 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT team_inquiry_channel_id FROM inquiry_settings 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[0]:
                        return result[0]
                    return None
                    
        except Exception as e:
            print(f"❌ 문의 채널 조회 실패: {e}")
            return None


    async def get_inquiry_settings(self, guild_id: str) -> dict:
        """서버의 문의 시스템 설정 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM inquiry_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    else:
                        # 기본값 반환
                        return {
                            'guild_id': guild_id,
                            'team_inquiry_channel_id': None,
                            'allowed_categories': '일반,건의,버그,계정,기타',
                            'daily_limit': 3,
                            'enable_anonymous': True,
                            'enable_private_inquiry': True,
                            'notification_role_id': None
                        }
                        
        except Exception as e:
            print(f"❌ 문의 설정 조회 실패: {e}")
            return {}


    async def get_next_ticket_number(self, guild_id: str) -> str:
        """다음 티켓 번호 생성 (관리팀 문의 + 1:1 상담 모두 고려)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 1. inquiries 테이블에서 마지막 티켓 번호 조회
                async with db.execute('''
                    SELECT ticket_number FROM inquiries 
                    WHERE guild_id = ? 
                    ORDER BY id DESC LIMIT 1
                ''', (guild_id,)) as cursor:
                    inquiry_result = await cursor.fetchone()
                
                # 2. consultations 테이블에서 마지막 티켓 번호 조회
                async with db.execute('''
                    SELECT ticket_number FROM consultations 
                    WHERE guild_id = ? 
                    ORDER BY id DESC LIMIT 1
                ''', (guild_id,)) as cursor:
                    consultation_result = await cursor.fetchone()
                
                # 3. 두 테이블의 티켓 번호 중 더 큰 값 사용
                max_number = 0
                
                if inquiry_result and inquiry_result[0]:
                    inquiry_num = int(inquiry_result[0].replace('#', ''))
                    max_number = max(max_number, inquiry_num)
                
                if consultation_result and consultation_result[0]:
                    consultation_num = int(consultation_result[0].replace('#', ''))
                    max_number = max(max_number, consultation_num)
                
                # 4. 다음 번호 생성
                new_number = max_number + 1
                
                return f"#{new_number:04d}"  # #0001 형식
                
        except Exception as e:
            print(f"❌ 티켓 번호 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return "#0001"


    async def get_inquiry_stats(self, guild_id: str) -> dict:
        """서버의 문의 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # 전체 문의 수
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['total'] = row[0] if row else 0
                
                # 대기 중
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'pending'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['pending'] = row[0] if row else 0
                
                # 처리 중
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'processing'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['processing'] = row[0] if row else 0
                
                # 완료
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'completed'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['completed'] = row[0] if row else 0
                
                # 관리팀 문의
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND inquiry_type = 'team'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['team_inquiries'] = row[0] if row else 0
                
                # 1:1 상담
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND inquiry_type = 'private'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['private_inquiries'] = row[0] if row else 0
                
                return stats
                
        except Exception as e:
            print(f"❌ 문의 통계 조회 실패: {e}")
            return {}

    async def save_inquiry(
        self,
        guild_id: str,
        ticket_number: str,
        user_id: str,
        username: str,
        inquiry_type: str,
        category: str,
        title: str,
        content: str,
        is_anonymous: bool,
        channel_message_id: str,
        assigned_to: str = None
    ) -> bool:
        """문의/티켓 저장"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                try:
                    await db.execute('''
                        INSERT INTO inquiries (
                            ticket_number, guild_id, user_id, username,
                            inquiry_type, category, title, content,
                            is_anonymous, status, assigned_to, channel_message_id,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (
                        ticket_number, guild_id, user_id, username,
                        inquiry_type, category, title, content,
                        is_anonymous, assigned_to, channel_message_id
                    ))
                    
                    await db.commit()
                    print(f"✅ 문의 저장 완료: {ticket_number}")
                    return True
                    
                except Exception as e:
                    # 🆕 트랜잭션 롤백
                    await db.rollback()
                    print(f"❌ 문의 DB 저장 실패 (롤백됨): {e}")
                    raise
                    
        except Exception as e:
            print(f"❌ 문의 저장 실패: {e}")
            return False

    async def update_inquiry_status(
        self,
        guild_id: str,
        ticket_number: str,
        new_status: str,
        admin_id: str = None
    ) -> bool:
        """문의 상태 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                if new_status == 'completed':
                    # 완료 시간 기록
                    await db.execute('''
                        UPDATE inquiries
                        SET status = ?, resolved_at = CURRENT_TIMESTAMP,
                            resolved_by = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, admin_id, guild_id, ticket_number))
                elif new_status == 'processing':
                    # 담당자 배정
                    await db.execute('''
                        UPDATE inquiries
                        SET status = ?, assigned_to = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, admin_id, guild_id, ticket_number))
                else:
                    # 일반 상태 업데이트
                    await db.execute('''
                        UPDATE inquiries
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, guild_id, ticket_number))
                
                await db.commit()
                print(f"✅ 문의 상태 업데이트: {ticket_number} → {new_status}")
                return True
                
        except Exception as e:
            print(f"❌ 문의 상태 업데이트 실패: {e}")
            return False


    async def add_inquiry_log(
        self,
        guild_id: str,
        ticket_number: str,
        admin_id: str,
        admin_name: str,
        action: str,
        details: str = None
    ) -> bool:
        """문의 로그 추가"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 문의 ID 조회
                async with db.execute('''
                    SELECT id FROM inquiries
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        print(f"❌ 문의를 찾을 수 없음: {ticket_number}")
                        return False
                    
                    inquiry_id = row[0]
                
                # 로그 추가
                await db.execute('''
                    INSERT INTO inquiry_logs (
                        inquiry_id, admin_id, admin_name, action, details, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (inquiry_id, admin_id, admin_name, action, details))
                
                await db.commit()
                print(f"✅ 문의 로그 추가: {ticket_number} - {action}")
                return True
                
        except Exception as e:
            print(f"❌ 문의 로그 추가 실패: {e}")
            return False


    async def add_reveal_log(
        self,
        guild_id: str,
        ticket_number: str,
        admin_id: str,
        admin_name: str
    ) -> bool:
        """익명 작성자 확인 로그 추가"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 문의 ID 조회
                async with db.execute('''
                    SELECT id FROM inquiries
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        return False
                    
                    inquiry_id = row[0]
                
                # 확인 로그 추가
                await db.execute('''
                    INSERT INTO inquiry_reveal_logs (
                        inquiry_id, admin_id, admin_name, revealed_at
                    )
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (inquiry_id, admin_id, admin_name))
                
                await db.commit()
                print(f"✅ 익명 작성자 확인 로그: {ticket_number} by {admin_name}")
                return True
                
        except Exception as e:
            print(f"❌ 익명 확인 로그 추가 실패: {e}")
            return False


    async def get_user_daily_inquiry_count(self, guild_id: str, user_id: str) -> int:
        """사용자의 오늘 문의 횟수 조회 (한국 시간 기준)"""
        try:
            from datetime import datetime, timedelta, timezone
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # ✅ 한국 시간(KST = UTC+9) 기준 오늘 00:00:00
                kst = timezone(timedelta(hours=9))
                now_kst = datetime.now(kst)
                today_start_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # UTC로 변환 (DB는 UTC로 저장됨)
                today_start_utc = today_start_kst.astimezone(timezone.utc)
                
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries
                    WHERE guild_id = ? AND user_id = ?
                    AND created_at >= ?
                    AND inquiry_type = 'team'
                ''', (guild_id, user_id, today_start_utc.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            print(f"❌ 일일 문의 횟수 조회 실패: {e}")
            return 0


    async def get_inquiry_by_ticket(self, guild_id: str, ticket_number: str) -> Optional[dict]:
        """티켓 번호로 문의 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM inquiries
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
                    
        except Exception as e:
            print(f"❌ 문의 조회 실패: {e}")
            return None


    async def get_user_inquiries(
        self,
        guild_id: str,
        user_id: str,
        limit: int = 10,
        status: str = None
    ) -> List[dict]:
        """사용자의 문의 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                if status:
                    query = '''
                        SELECT * FROM inquiries
                        WHERE guild_id = ? AND user_id = ? AND status = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, user_id, status, limit)
                else:
                    query = '''
                        SELECT * FROM inquiries
                        WHERE guild_id = ? AND user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, user_id, limit)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"❌ 사용자 문의 목록 조회 실패: {e}")
            return []


    async def get_inquiry_logs(self, guild_id: str, ticket_number: str) -> List[dict]:
        """문의 로그 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # 문의 ID 조회
                async with db.execute('''
                    SELECT id FROM inquiries
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        return []
                    
                    inquiry_id = row[0]
                
                # 로그 조회
                async with db.execute('''
                    SELECT * FROM inquiry_logs
                    WHERE inquiry_id = ?
                    ORDER BY created_at DESC
                ''', (inquiry_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"❌ 문의 로그 조회 실패: {e}")
            return []


    async def get_reveal_logs(self, guild_id: str, ticket_number: str) -> List[dict]:
        """익명 작성자 확인 로그 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                # 문의 ID 조회
                async with db.execute('''
                    SELECT id FROM inquiries
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        return []
                    
                    inquiry_id = row[0]
                
                # 확인 로그 조회
                async with db.execute('''
                    SELECT * FROM inquiry_reveal_logs
                    WHERE inquiry_id = ?
                    ORDER BY revealed_at DESC
                ''', (inquiry_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"❌ 확인 로그 조회 실패: {e}")
            return []

    async def save_consultation(
        self,
        guild_id: str,
        ticket_number: str,
        user_id: str,
        username: str,
        admin_id: str,
        admin_name: str,
        category: str,
        content: str,
        is_urgent: bool,
        request_message_id: str
    ) -> bool:
        """상담 요청 저장"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                try:
                    await db.execute('''
                        INSERT INTO consultations (
                            ticket_number, guild_id, user_id, username,
                            admin_id, admin_name, category, content,
                            is_urgent, status, request_message_id,
                            created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (
                        ticket_number, guild_id, user_id, username,
                        admin_id, admin_name, category, content,
                        is_urgent, request_message_id
                    ))
                    
                    await db.commit()
                    print(f"✅ 상담 요청 저장: {ticket_number}")
                    return True
                    
                except Exception as e:
                    # 🆕 트랜잭션 롤백
                    await db.rollback()
                    print(f"❌ 상담 DB 저장 실패 (롤백됨): {e}")
                    raise
                    
        except Exception as e:
            print(f"❌ 상담 요청 저장 실패: {e}")
            return False


    async def update_consultation_status(
        self,
        guild_id: str,
        ticket_number: str,
        new_status: str,
        admin_id: str = None
    ) -> bool:
        """상담 상태 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                if new_status == 'accepted':
                    await db.execute('''
                        UPDATE consultations
                        SET status = ?, accepted_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, guild_id, ticket_number))
                elif new_status == 'completed':
                    await db.execute('''
                        UPDATE consultations
                        SET status = ?, completed_at = CURRENT_TIMESTAMP,
                            completed_by = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, admin_id, guild_id, ticket_number))
                else:
                    await db.execute('''
                        UPDATE consultations
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND ticket_number = ?
                    ''', (new_status, guild_id, ticket_number))
                
                await db.commit()
                print(f"✅ 상담 상태 업데이트: {ticket_number} → {new_status}")
                return True
                
        except Exception as e:
            print(f"❌ 상담 상태 업데이트 실패: {e}")
            return False


    async def get_consultation_by_ticket(self, guild_id: str, ticket_number: str) -> Optional[dict]:
        """티켓 번호로 상담 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM consultations
                    WHERE guild_id = ? AND ticket_number = ?
                ''', (guild_id, ticket_number)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
                    
        except Exception as e:
            print(f"❌ 상담 조회 실패: {e}")
            return None


    async def get_user_active_consultation(self, guild_id: str, user_id: str) -> Optional[dict]:
        """사용자의 진행 중인 상담 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM consultations
                    WHERE guild_id = ? AND user_id = ?
                    AND status IN ('pending', 'accepted')
                    ORDER BY created_at DESC
                    LIMIT 1
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        columns = [desc[0] for desc in cursor.description]
                        return dict(zip(columns, row))
                    return None
                    
        except Exception as e:
            print(f"❌ 진행 중인 상담 조회 실패: {e}")
            return None


    async def get_available_admins(self, guild_id: str) -> List[dict]:
        """상담 가능한 관리자 목록 조회
        
        현재는 서버의 관리자 권한을 가진 멤버들을 반환합니다.
        추후 별도 설정으로 확장 가능
        """
        try:
            from discord import Guild
            
            # bot 인스턴스에서 guild 가져오기
            # 이 메서드는 bot.db_manager를 통해 호출되므로 bot 참조 필요
            # 실제로는 Cog에서 guild를 전달받아 사용하는 것이 좋음
            
            # 간단한 구현: 빈 리스트 반환 (Cog에서 직접 처리)
            return []
            
        except Exception as e:
            print(f"❌ 관리자 목록 조회 실패: {e}")
            return []


    async def get_consultation_stats(self, guild_id: str) -> dict:
        """서버의 상담 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                stats = {}
                
                # 전체 상담 수
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['total'] = row[0] if row else 0
                
                # 대기 중
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations 
                    WHERE guild_id = ? AND status = 'pending'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['pending'] = row[0] if row else 0
                
                # 수락됨
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations 
                    WHERE guild_id = ? AND status = 'accepted'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['accepted'] = row[0] if row else 0
                
                # 거절됨
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations 
                    WHERE guild_id = ? AND status = 'rejected'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['rejected'] = row[0] if row else 0
                
                # 완료됨
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations 
                    WHERE guild_id = ? AND status = 'completed'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['completed'] = row[0] if row else 0
                
                return stats
                
        except Exception as e:
            print(f"❌ 상담 통계 조회 실패: {e}")
            return {}


    async def get_user_consultations(
        self,
        guild_id: str,
        user_id: str,
        limit: int = 10,
        status: str = None
    ) -> List[dict]:
        """사용자의 상담 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                if status:
                    query = '''
                        SELECT * FROM consultations
                        WHERE guild_id = ? AND user_id = ? AND status = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, user_id, status, limit)
                else:
                    query = '''
                        SELECT * FROM consultations
                        WHERE guild_id = ? AND user_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, user_id, limit)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"❌ 사용자 상담 목록 조회 실패: {e}")
            return []


    async def get_admin_consultations(
        self,
        guild_id: str,
        admin_id: str,
        limit: int = 10,
        status: str = None
    ) -> List[dict]:
        """관리자의 상담 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                if status:
                    query = '''
                        SELECT * FROM consultations
                        WHERE guild_id = ? AND admin_id = ? AND status = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, admin_id, status, limit)
                else:
                    query = '''
                        SELECT * FROM consultations
                        WHERE guild_id = ? AND admin_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                    '''
                    params = (guild_id, admin_id, limit)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                    
        except Exception as e:
            print(f"❌ 관리자 상담 목록 조회 실패: {e}")
            return []


    # 추가: inquiry_stats 업데이트 (1:1 상담 포함)
    async def get_inquiry_stats(self, guild_id: str) -> dict:
        """서버의 문의 통계 조회 (관리팀 문의 + 1:1 상담)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                stats = {}
                
                # 관리팀 문의 통계
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['total'] = row[0] if row else 0
                
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'pending'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['pending'] = row[0] if row else 0
                
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'processing'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['processing'] = row[0] if row else 0
                
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND status = 'completed'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['completed'] = row[0] if row else 0
                
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries 
                    WHERE guild_id = ? AND inquiry_type = 'team'
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['team_inquiries'] = row[0] if row else 0
                
                # 1:1 상담 통계 추가
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations 
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    stats['private_inquiries'] = row[0] if row else 0
                
                return stats
                
        except Exception as e:
            print(f"❌ 문의 통계 조회 실패: {e}")
            return {}

    async def get_active_inquiries(self, guild_id: str) -> List[dict]:
        """활성 상태의 문의 목록 조회 (View 복원용)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM inquiries
                    WHERE guild_id = ? AND status IN ('pending', 'processing')
                    ORDER BY created_at DESC
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"❌ 활성 문의 조회 실패: {e}")
            return []


    async def get_active_consultations(self, guild_id: str) -> List[dict]:
        """활성 상태의 상담 목록 조회 (View 복원용)"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM consultations
                    WHERE guild_id = ? AND status IN ('pending', 'accepted')
                    ORDER BY created_at DESC
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"❌ 활성 상담 조회 실패: {e}")
            return []

    async def get_server_admins(self, guild_id: str) -> List[dict]:
        """서버 관리자 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT * FROM server_admins
                    WHERE guild_id = ? AND is_active = TRUE
                    ORDER BY added_at DESC
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"❌ 서버 관리자 조회 실패: {e}")
            return []

    async def check_inquiry_spam(self, guild_id: str, user_id: str) -> dict:
        """문의 스팸 체크"""
        try:
            from datetime import datetime, timedelta
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                now = datetime.utcnow()
                one_hour_ago = now - timedelta(hours=1)
                one_day_ago = now - timedelta(days=1)
                
                # 1시간 내 문의 수
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries
                    WHERE guild_id = ? AND user_id = ?
                    AND created_at >= ?
                ''', (guild_id, user_id, one_hour_ago.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    hour_count = row[0] if row else 0
                
                # 1일 내 문의 수
                async with db.execute('''
                    SELECT COUNT(*) FROM inquiries
                    WHERE guild_id = ? AND user_id = ?
                    AND created_at >= ?
                ''', (guild_id, user_id, one_day_ago.isoformat())) as cursor:
                    row = await cursor.fetchone()
                    day_count = row[0] if row else 0
                
                # 최근 문의 내용 (유사도 체크용)
                async with db.execute('''
                    SELECT content FROM inquiries
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 5
                ''', (guild_id, user_id)) as cursor:
                    recent_contents = [row[0] for row in await cursor.fetchall()]
                
                return {
                    'hour_count': hour_count,
                    'day_count': day_count,
                    'recent_contents': recent_contents,
                    'is_spam': hour_count >= 5 or day_count >= 15
                }
                
        except Exception as e:
            print(f"❌ 스팸 체크 실패: {e}")
            return {
                'hour_count': 0,
                'day_count': 0,
                'recent_contents': [],
                'is_spam': False
            }

    async def add_inquiry_cooldown(self, guild_id: str, user_id: str, hours: int = 1):
        """문의 쿨다운 추가"""
        try:
            from datetime import datetime, timedelta
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                cooldown_until = datetime.now() + timedelta(hours=hours)
                
                await db.execute('''
                    INSERT OR REPLACE INTO inquiry_cooldowns (
                        guild_id, user_id, cooldown_until, reason
                    )
                    VALUES (?, ?, ?, ?)
                ''', (guild_id, user_id, cooldown_until.isoformat(), 'spam_detection'))
                
                await db.commit()
                print(f"⏰ 쿨다운 추가: {user_id} ({hours}시간)")
                return True
                
        except Exception as e:
            print(f"❌ 쿨다운 추가 실패: {e}")
            return False

    async def check_inquiry_cooldown(self, guild_id: str, user_id: str) -> dict:
        """문의 쿨다운 체크"""
        try:
            from datetime import datetime
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT cooldown_until, reason FROM inquiry_cooldowns
                    WHERE guild_id = ? AND user_id = ?
                    AND cooldown_until > ?
                ''', (guild_id, user_id, datetime.utcnow().isoformat())) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        cooldown_until = datetime.fromisoformat(row[0])
                        remaining = cooldown_until - datetime.utcnow()
                        
                        return {
                            'is_cooldown': True,
                            'cooldown_until': cooldown_until,
                            'remaining_minutes': int(remaining.total_seconds() / 60),
                            'reason': row[1]
                        }
                    
                    return {'is_cooldown': False}
                    
        except Exception as e:
            print(f"❌ 쿨다운 체크 실패: {e}")
            return {'is_cooldown': False}

    async def cleanup_stale_consultations(self, hours: int = 72):
        """오래된 상담 자동 정리 (72시간 이상 응답 없음)"""
        try:
            from datetime import datetime, timedelta, timezone
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # pending 상태 72시간 이상
                await db.execute('''
                    UPDATE consultations
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP,
                        completed_by = 'system_timeout'
                    WHERE status = 'pending'
                    AND datetime(created_at) < ?
                ''', (cutoff_time.isoformat(),))
                
                # accepted 상태 72시간 이상 업데이트 없음
                await db.execute('''
                    UPDATE consultations
                    SET status = 'completed',
                        completed_at = CURRENT_TIMESTAMP,
                        completed_by = 'system_timeout'
                    WHERE status = 'accepted'
                    AND datetime(updated_at) < ?
                ''', (cutoff_time.isoformat(),))
                
                await db.commit()
                
                # 정리된 개수 확인
                async with db.execute('''
                    SELECT COUNT(*) FROM consultations
                    WHERE completed_by = 'system_timeout'
                    AND datetime(completed_at) > ?
                ''', (cutoff_time.isoformat(),)) as cursor:
                    row = await cursor.fetchone()
                    cleaned_count = row[0] if row else 0
                
                if cleaned_count > 0:
                    logger.info(f"🧹 오래된 상담 {cleaned_count}개 자동 정리")
                
                return cleaned_count
                
        except Exception as e:
            logger.error(f"❌ 상담 정리 실패: {e}")
            return 0

    async def set_tts_dedicated_channel(
        self, 
        guild_id: str, 
        channel_id: Optional[str]
    ) -> bool:
        """TTS 전용 채널 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    '''
                    INSERT INTO tts_channel_settings (guild_id, dedicated_channel_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        dedicated_channel_id = excluded.dedicated_channel_id,
                        updated_at = CURRENT_TIMESTAMP
                    ''',
                    (guild_id, channel_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ TTS 전용 채널 설정 실패: {e}")
            return False

    async def get_tts_dedicated_channel(self, guild_id: str) -> str:
        """TTS 전용 채널 ID 조회"""
        try:
            async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT dedicated_channel_id FROM tts_channel_settings
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row and row[0] else None
                    
        except Exception as e:
            print(f"❌ TTS 전용 채널 조회 실패: {e}")
            return None

    async def get_tts_channel_settings(self, guild_id: str) -> Optional[Dict[str, Any]]:
        """TTS 전용 채널 설정 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''
                SELECT dedicated_channel_id, auto_filter_short_reactions, 
                    min_message_length, filter_emoji_only, filter_bot_messages
                FROM tts_channel_settings
                WHERE guild_id = ?
                ''',
                (guild_id,)
            )
            result = await cursor.fetchone()
            
            if result:
                return {
                    'channel_id': result[0],
                    'filter_short': bool(result[1]),
                    'min_length': result[2],
                    'filter_emoji': bool(result[3]),
                    'filter_bot': bool(result[4])
                }
            return None

    async def set_user_tts_preference(
        self, 
        guild_id: str, 
        user_id: str, 
        voice: str,
        rate: str = '+0%',
        pitch: str = '+0Hz',
        volume: str = '+0%'
    ) -> bool:
        """사용자의 TTS 설정 저장"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    '''
                    INSERT INTO user_tts_preferences 
                    (guild_id, user_id, default_voice, default_rate, default_pitch, default_volume, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        default_voice = excluded.default_voice,
                        default_rate = excluded.default_rate,
                        default_pitch = excluded.default_pitch,
                        default_volume = excluded.default_volume,
                        updated_at = CURRENT_TIMESTAMP
                    ''',
                    (guild_id, user_id, voice, rate, pitch, volume)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"❌ TTS 설정 저장 실패: {e}")
            return False

    async def get_user_tts_preference(self, guild_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자의 TTS 설정 조회"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''
                SELECT default_voice, default_rate, default_pitch, default_volume
                FROM user_tts_preferences
                WHERE guild_id = ? AND user_id = ?
                ''',
                (guild_id, user_id)
            )
            result = await cursor.fetchone()
            
            if result:
                return {
                    'voice': result[0],
                    'rate': result[1],
                    'pitch': result[2],
                    'volume': result[3]
                }
            return None

    async def create_auto_schedule(
        self, 
        guild_id: str, 
        schedule_name: str,
        day_of_week: int,
        scrim_time: str,
        recruitment_title: str,
        recruitment_description: str,
        deadline_type: str,
        deadline_value: str,
        channel_id: str,
        send_dm: bool,
        created_by: str,
        post_days_before: int = 0,  # 🆕
        recurrence_interval: int = 1,  # 🆕
        reminder_enabled: bool = False,  # 🆕
        reminder_hours_before: int = 5  # 🆕
    ) -> bool:
        """정기 내전 자동 스케줄 생성"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO scrim_auto_schedules 
                    (guild_id, schedule_name, day_of_week, scrim_time, 
                    recruitment_title, recruitment_description, 
                    deadline_type, deadline_value, channel_id, 
                    send_dm_notification, created_by,
                    post_days_before, recurrence_interval,
                    reminder_enabled, reminder_hours_before)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    guild_id, schedule_name, day_of_week, scrim_time,
                    recruitment_title, recruitment_description,
                    deadline_type, deadline_value, channel_id,
                    send_dm, created_by,
                    post_days_before, recurrence_interval,
                    reminder_enabled, reminder_hours_before
                ))
                await db.commit()
                print(f"✅ 자동 스케줄 생성 완료: {schedule_name}")
                return True
        except Exception as e:
            print(f"❌ 자동 스케줄 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            return False


    async def get_auto_schedules(self, guild_id: str) -> List[Dict]:
        """서버의 모든 자동 스케줄 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_auto_schedules 
                    WHERE guild_id = ?
                    ORDER BY day_of_week ASC, scrim_time ASC
                ''', (guild_id,)) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"❌ 자동 스케줄 조회 실패: {e}")
            return []


    async def get_active_auto_schedules(self, day_of_week: int = None) -> List[Dict]:
        """활성 자동 스케줄 조회 (특정 요일 또는 전체)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if day_of_week is not None:
                    query = '''
                        SELECT * FROM scrim_auto_schedules 
                        WHERE is_active = TRUE AND day_of_week = ?
                        ORDER BY guild_id, scrim_time ASC
                    '''
                    params = (day_of_week,)
                else:
                    query = '''
                        SELECT * FROM scrim_auto_schedules 
                        WHERE is_active = TRUE
                        ORDER BY guild_id, day_of_week, scrim_time ASC
                    '''
                    params = ()
                
                async with db.execute(query, params) as cursor:
                    results = await cursor.fetchall()
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in results]
        except Exception as e:
            print(f"❌ 활성 스케줄 조회 실패: {e}")
            return []


    async def update_schedule_last_created(self, schedule_id: int, date_str: str) -> bool:
        """스케줄의 마지막 생성 날짜 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scrim_auto_schedules 
                    SET last_created_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (date_str, schedule_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 마지막 생성 날짜 업데이트 실패: {e}")
            return False


    async def toggle_schedule_status(self, schedule_id: int, is_active: bool) -> bool:
        """스케줄 활성화/비활성화 토글"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE scrim_auto_schedules 
                    SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (is_active, schedule_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 스케줄 상태 변경 실패: {e}")
            return False


    async def delete_auto_schedule(self, schedule_id: int, guild_id: str) -> bool:
        """자동 스케줄 삭제"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    DELETE FROM scrim_auto_schedules 
                    WHERE id = ? AND guild_id = ?
                ''', (schedule_id, guild_id))
                await db.commit()
                return True
        except Exception as e:
            print(f"❌ 스케줄 삭제 실패: {e}")
            return False


    async def get_schedule_by_id(self, schedule_id: int) -> Optional[Dict]:
        """ID로 스케줄 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT * FROM scrim_auto_schedules WHERE id = ?
                ''', (schedule_id,)) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        columns = [description[0] for description in cursor.description]
                        return dict(zip(columns, result))
                    return None
        except Exception as e:
            print(f"❌ 스케줄 조회 실패: {e}")
            return None

    async def create_event_team(
        self, 
        guild_id: str, 
        team_name: str, 
        member_ids: list,  # [(user_id, username), ...]
        created_by: str
    ) -> tuple[bool, str]:
        """이벤트 팀 생성
        
        Returns:
            (성공여부, 팀ID 또는 에러메시지)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 팀명 중복 체크
                async with db.execute('''
                    SELECT team_id FROM event_teams 
                    WHERE guild_id = ? AND team_name = ? AND is_active = TRUE
                ''', (guild_id, team_name)) as cursor:
                    if await cursor.fetchone():
                        return False, f"'{team_name}' 팀이 이미 존재합니다"
                
                # 팀 ID 생성
                team_id = self.generate_uuid()
                
                # 팀 생성
                await db.execute('''
                    INSERT INTO event_teams (team_id, guild_id, team_name, created_by)
                    VALUES (?, ?, ?, ?)
                ''', (team_id, guild_id, team_name, created_by))
                
                # 팀원 추가
                for user_id, username in member_ids:
                    await db.execute('''
                        INSERT INTO event_team_members (team_id, user_id, username)
                        VALUES (?, ?, ?)
                    ''', (team_id, user_id, username))
                
                await db.commit()
                print(f"✅ 팀 생성 완료: {team_name} (ID: {team_id})")
                return True, team_id
                
        except Exception as e:
            print(f"❌ 팀 생성 실패: {e}")
            return False, str(e)

    async def get_event_teams(self, guild_id: str) -> list:
        """서버의 모든 활성 팀 목록 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        t.team_id,
                        t.team_name,
                        t.created_at,
                        COUNT(m.user_id) as member_count
                    FROM event_teams t
                    LEFT JOIN event_team_members m ON t.team_id = m.team_id
                    WHERE t.guild_id = ? AND t.is_active = TRUE
                    GROUP BY t.team_id
                    ORDER BY t.team_name
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    teams = []
                    for row in rows:
                        teams.append({
                            'team_id': row[0],
                            'team_name': row[1],
                            'created_at': row[2],
                            'member_count': row[3]
                        })
                    
                    return teams
                    
        except Exception as e:
            print(f"❌ 팀 목록 조회 실패: {e}")
            return []

    async def get_event_team_details(self, team_id: str) -> dict:
        """특정 팀의 상세 정보 (팀원 포함)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 팀 기본 정보
                async with db.execute('''
                    SELECT team_id, guild_id, team_name, created_by, created_at
                    FROM event_teams
                    WHERE team_id = ? AND is_active = TRUE
                ''', (team_id,)) as cursor:
                    team_row = await cursor.fetchone()
                    
                    if not team_row:
                        return None
                    
                    team_info = {
                        'team_id': team_row[0],
                        'guild_id': team_row[1],
                        'team_name': team_row[2],
                        'created_by': team_row[3],
                        'created_at': team_row[4],
                        'members': []
                    }
                
                # 팀원 목록
                async with db.execute('''
                    SELECT user_id, username, joined_at
                    FROM event_team_members
                    WHERE team_id = ?
                    ORDER BY joined_at
                ''', (team_id,)) as cursor:
                    member_rows = await cursor.fetchall()
                    
                    for row in member_rows:
                        team_info['members'].append({
                            'user_id': row[0],
                            'username': row[1],
                            'joined_at': row[2]
                        })
                    
                    return team_info
                    
        except Exception as e:
            print(f"❌ 팀 상세 정보 조회 실패: {e}")
            return None

    async def add_team_member(
        self, 
        team_id: str, 
        user_id: str, 
        username: str
    ) -> tuple[bool, str]:
        """팀에 새 팀원 추가"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 이미 팀원인지 체크
                async with db.execute('''
                    SELECT id FROM event_team_members
                    WHERE team_id = ? AND user_id = ?
                ''', (team_id, user_id)) as cursor:
                    if await cursor.fetchone():
                        return False, "이미 팀원입니다"
                
                # 팀원 추가
                await db.execute('''
                    INSERT INTO event_team_members (team_id, user_id, username)
                    VALUES (?, ?, ?)
                ''', (team_id, user_id, username))
                
                await db.commit()
                return True, "팀원이 추가되었습니다"
                
        except Exception as e:
            print(f"❌ 팀원 추가 실패: {e}")
            return False, str(e)

    async def remove_team_member(self, team_id: str, user_id: str) -> tuple[bool, str]:
        """팀에서 팀원 제거"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                cursor = await db.execute('''
                    DELETE FROM event_team_members
                    WHERE team_id = ? AND user_id = ?
                ''', (team_id, user_id))
                
                await db.commit()
                
                if cursor.rowcount == 0:
                    return False, "해당 유저가 팀원이 아닙니다"
                
                return True, "팀원이 제거되었습니다"
                
        except Exception as e:
            print(f"❌ 팀원 제거 실패: {e}")
            return False, str(e)

    async def delete_event_team(self, team_id: str) -> tuple[bool, str]:
        """팀 비활성화 (완전 삭제 대신 is_active=FALSE)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                cursor = await db.execute('''
                    UPDATE event_teams
                    SET is_active = FALSE
                    WHERE team_id = ?
                ''', (team_id,))
                
                await db.commit()
                
                if cursor.rowcount == 0:
                    return False, "팀을 찾을 수 없습니다"
                
                return True, "팀이 삭제되었습니다"
                
        except Exception as e:
            print(f"❌ 팀 삭제 실패: {e}")
            return False, str(e)

    async def get_user_event_team(self, guild_id: str, user_id: str) -> dict:
        """유저가 속한 이벤트 팀 정보 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        t.team_id,
                        t.team_name,
                        t.guild_id
                    FROM event_teams t
                    JOIN event_team_members m ON t.team_id = m.team_id
                    WHERE t.guild_id = ? AND m.user_id = ? AND t.is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        team_id = row[0]
                        
                        # 팀의 총 점수 계산 (미션 + 음성)
                        async with db.execute('''
                            SELECT COALESCE(SUM(awarded_points), 0)
                            FROM event_mission_completions
                            WHERE team_id = ?
                        ''', (team_id,)) as score_cursor:
                            score_row = await score_cursor.fetchone()
                            mission_score = score_row[0] if score_row else 0
                        
                        # 음성 점수
                        async with db.execute('''
                            SELECT COALESCE(SUM(total_score), 0)
                            FROM voice_team_daily_scores
                            WHERE team_id = ?
                        ''', (team_id,)) as voice_cursor:
                            voice_row = await voice_cursor.fetchone()
                            voice_score = voice_row[0] if voice_row else 0
                        
                        return {
                            'team_id': team_id,
                            'team_name': row[1],
                            'guild_id': row[2],
                            'total_score': mission_score + voice_score,
                            'mission_score': mission_score,
                            'voice_score': voice_score
                        }
                    
                    return None
                    
        except Exception as e:
            print(f"❌ 유저 이벤트 팀 조회 실패: {e}")
            return None

    async def create_event_mission(
        self,
        guild_id: str,
        mission_name: str,
        description: str,
        base_points: int,
        category: str,  # 'daily', 'offline', 'online', 'hidden'
        min_participants: int = 1,
        bonus_conditions: dict = None
    ) -> tuple[bool, str]:
        """이벤트 미션 생성
        
        Args:
            bonus_conditions: {"all_clear_bonus": 5, "four_players_bonus": 1}
        
        Returns:
            (성공여부, 미션ID 또는 에러메시지)
        """
        try:
            import json
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 미션명 중복 체크
                async with db.execute('''
                    SELECT mission_id FROM event_missions
                    WHERE guild_id = ? AND mission_name = ? AND is_active = TRUE
                ''', (guild_id, mission_name)) as cursor:
                    if await cursor.fetchone():
                        return False, f"'{mission_name}' 미션이 이미 존재합니다"
                
                # 미션 ID 생성
                mission_id = self.generate_uuid()
                
                # bonus_conditions를 JSON 문자열로 변환
                bonus_json = json.dumps(bonus_conditions) if bonus_conditions else None
                
                # 미션 생성
                await db.execute('''
                    INSERT INTO event_missions (
                        mission_id, guild_id, mission_name, description,
                        base_points, category, min_participants, bonus_conditions
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (mission_id, guild_id, mission_name, description,
                    base_points, category, min_participants, bonus_json))
                
                await db.commit()
                print(f"✅ 미션 생성 완료: {mission_name} (ID: {mission_id})")
                return True, mission_id
                
        except Exception as e:
            print(f"❌ 미션 생성 실패: {e}")
            return False, str(e)

    async def get_event_missions(
        self, 
        guild_id: str, 
        category: str = None
    ) -> list:
        """서버의 미션 목록 조회
        
        Args:
            category: 'daily', 'offline', 'online', 'hidden' 또는 None (전체)
        """
        try:
            import json
            
            async with aiosqlite.connect(self.db_path) as db:
                if category:
                    query = '''
                        SELECT 
                            mission_id, mission_name, description, base_points,
                            category, min_participants, bonus_conditions, created_at
                        FROM event_missions
                        WHERE guild_id = ? AND category = ? AND is_active = TRUE
                        ORDER BY base_points DESC, mission_name
                    '''
                    params = (guild_id, category)
                else:
                    query = '''
                        SELECT 
                            mission_id, mission_name, description, base_points,
                            category, min_participants, bonus_conditions, created_at
                        FROM event_missions
                        WHERE guild_id = ? AND is_active = TRUE
                        ORDER BY 
                            CASE category
                                WHEN 'daily' THEN 1
                                WHEN 'online' THEN 2
                                WHEN 'offline' THEN 3
                                WHEN 'hidden' THEN 4
                            END,
                            base_points DESC
                    '''
                    params = (guild_id,)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    missions = []
                    for row in rows:
                        bonus = json.loads(row[6]) if row[6] else {}
                        
                        missions.append({
                            'mission_id': row[0],
                            'mission_name': row[1],
                            'description': row[2],
                            'base_points': row[3],
                            'category': row[4],
                            'min_participants': row[5],
                            'bonus_conditions': bonus,
                            'created_at': row[7]
                        })
                    
                    return missions
                    
        except Exception as e:
            print(f"❌ 미션 목록 조회 실패: {e}")
            return []

    async def get_event_mission_details(self, mission_id: str) -> dict:
        """특정 미션의 상세 정보"""
        try:
            import json
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        mission_id, guild_id, mission_name, description,
                        base_points, category, min_participants, 
                        bonus_conditions, created_at
                    FROM event_missions
                    WHERE mission_id = ? AND is_active = TRUE
                ''', (mission_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        return None
                    
                    bonus = json.loads(row[7]) if row[7] else {}
                    
                    return {
                        'mission_id': row[0],
                        'guild_id': row[1],
                        'mission_name': row[2],
                        'description': row[3],
                        'base_points': row[4],
                        'category': row[5],
                        'min_participants': row[6],
                        'bonus_conditions': bonus,
                        'created_at': row[8]
                    }
                    
        except Exception as e:
            print(f"❌ 미션 상세 정보 조회 실패: {e}")
            return None

    async def delete_event_mission(self, mission_id: str) -> tuple[bool, str]:
        """미션 비활성화"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                cursor = await db.execute('''
                    UPDATE event_missions
                    SET is_active = FALSE
                    WHERE mission_id = ?
                ''', (mission_id,))
                
                await db.commit()
                
                if cursor.rowcount == 0:
                    return False, "미션을 찾을 수 없습니다"
                
                return True, "미션이 삭제되었습니다"
                
        except Exception as e:
            print(f"❌ 미션 삭제 실패: {e}")
            return False, str(e)

    async def get_mission_stats(self, guild_id: str) -> dict:
        """카테고리별 미션 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        category,
                        COUNT(*) as count,
                        SUM(base_points) as total_points
                    FROM event_missions
                    WHERE guild_id = ? AND is_active = TRUE
                    GROUP BY category
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    stats = {
                        'daily': {'count': 0, 'total_points': 0},
                        'online': {'count': 0, 'total_points': 0},
                        'offline': {'count': 0, 'total_points': 0},
                        'hidden': {'count': 0, 'total_points': 0}
                    }
                    
                    for row in rows:
                        category = row[0]
                        stats[category] = {
                            'count': row[1],
                            'total_points': row[2]
                        }
                    
                    return stats
                    
        except Exception as e:
            print(f"❌ 미션 통계 조회 실패: {e}")
            return {}

    async def record_mission_completion(
        self,
        team_id: str,
        mission_id: str,
        participants_count: int,
        completed_by: str,
        notes: str = None
    ) -> tuple[bool, str, int]:
        """미션 완료 기록 및 점수 부여
        
        Returns:
            (성공여부, 메시지, 부여된점수)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 미션 정보 조회
                mission = await self.get_event_mission_details(mission_id)
                if not mission:
                    return False, "미션을 찾을 수 없습니다", 0
                
                # 최소 참여 인원 체크
                if participants_count < mission['min_participants']:
                    return False, f"최소 {mission['min_participants']}명 이상 참여해야 합니다", 0
                
                # 1. 일일 퀘스트인 경우 하루 1회 제한 체크
                if mission['category'] == 'daily':
                    from datetime import datetime
                    today = datetime.now().strftime('%Y-%m-%d')
                    
                    already_completed = await self.check_daily_mission_completed(
                        team_id, mission_id, today
                    )
                    
                    if already_completed:
                        return False, "❌ 오늘 이미 완료한 미션입니다", 0
                
                # 2. 기본 점수
                awarded_points = mission['base_points']
                
                # 3. 일일 퀘스트 4명 이상 참여 보너스
                if mission['category'] == 'daily' and participants_count >= 5:
                    awarded_points += 1
                    print(f"🎁 5명 이상 참여 보너스: +1점")
                
                # 4. 완료 ID 생성
                completion_id = self.generate_uuid()
                
                # 5. 완료 기록 저장
                await db.execute('''
                    INSERT INTO event_mission_completions (
                        completion_id, team_id, mission_id,
                        participants_count, awarded_points,
                        completed_by, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (completion_id, team_id, mission_id,
                    participants_count, awarded_points,
                    completed_by, notes))
                
                await db.commit()
                
                # 6. 일일 퀘스트 올클리어 보너스 체크 (하루 1회만)
                bonus_message = ""
                if mission['category'] == 'daily':
                    # 올클리어 달성 체크
                    all_clear, bonus = await self.check_daily_all_clear_bonus(team_id)
                    
                    if all_clear:
                        # 오늘 이미 보너스를 받았는지 체크
                        from datetime import datetime
                        today = datetime.now().strftime('%Y-%m-%d')
                        already_given = await self.check_daily_all_clear_bonus_already_given(
                            team_id, today
                        )
                        
                        if not already_given:
                            # 올클리어 보너스 별도 기록 (하루 1회만)
                            bonus_completion_id = self.generate_uuid()
                            
                            await db.execute('''
                                INSERT INTO event_mission_completions (
                                    completion_id, team_id, mission_id,
                                    participants_count, awarded_points,
                                    completed_by, notes
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            ''', (bonus_completion_id, team_id, 
                                'daily_all_clear_bonus',  # 특수 ID
                                participants_count, bonus,
                                completed_by, '일일 퀘스트 올클리어 보너스'))
                            
                            await db.commit()
                            
                            awarded_points += bonus
                            bonus_message = f"\n🎉 일일 퀘스트 올클리어! 보너스 +{bonus}점 추가!"
                            print(f"🎉 일일 올클리어 보너스: +{bonus}점")
                        else:
                            print(f"ℹ️ 올클리어 보너스는 오늘 이미 지급됨")
                
                print(f"✅ 미션 완료 기록: {mission['mission_name']} - {awarded_points}점")
                return True, f"미션 완료 처리되었습니다{bonus_message}", awarded_points
                
        except Exception as e:
            print(f"❌ 미션 완료 기록 실패: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e), 0

    async def get_team_total_score(self, team_id: str) -> int:
        """팀의 총 누적 점수 계산"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT SUM(awarded_points)
                    FROM event_mission_completions
                    WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row[0] else 0
                    
        except Exception as e:
            print(f"❌ 팀 총점 계산 실패: {e}")
            return 0

    async def get_team_mission_history(
        self, 
        team_id: str,
        limit: int = 20
    ) -> list:
        """팀의 미션 완료 이력"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        c.completion_id,
                        c.mission_id,
                        m.mission_name,
                        m.category,
                        c.participants_count,
                        c.awarded_points,
                        c.completed_at,
                        c.completed_by,
                        c.notes
                    FROM event_mission_completions c
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.team_id = ?
                    ORDER BY c.completed_at DESC
                    LIMIT ?
                ''', (team_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    history = []
                    for row in rows:
                        history.append({
                            'completion_id': row[0],
                            'mission_id': row[1],
                            'mission_name': row[2],
                            'category': row[3],
                            'participants_count': row[4],
                            'awarded_points': row[5],
                            'completed_at': row[6],
                            'completed_by': row[7],
                            'notes': row[8]
                        })
                    
                    return history
                    
        except Exception as e:
            print(f"❌ 팀 미션 이력 조회 실패: {e}")
            return []

    async def get_mission_completion_stats(self, mission_id: str) -> dict:
        """특정 미션의 완료 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        COUNT(*) as completion_count,
                        SUM(awarded_points) as total_points_awarded,
                        AVG(participants_count) as avg_participants
                    FROM event_mission_completions
                    WHERE mission_id = ?
                ''', (mission_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    return {
                        'completion_count': row[0] if row[0] else 0,
                        'total_points_awarded': row[1] if row[1] else 0,
                        'avg_participants': round(row[2], 1) if row[2] else 0
                    }
                    
        except Exception as e:
            print(f"❌ 미션 완료 통계 조회 실패: {e}")
            return {}

    async def get_team_category_stats(self, team_id: str) -> dict:
        """팀의 카테고리별 미션 완료 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        m.category,
                        COUNT(*) as completed_count,
                        SUM(c.awarded_points) as category_points
                    FROM event_mission_completions c
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.team_id = ?
                    GROUP BY m.category
                ''', (team_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    stats = {
                        'daily': {'count': 0, 'points': 0},
                        'online': {'count': 0, 'points': 0},
                        'offline': {'count': 0, 'points': 0},
                        'hidden': {'count': 0, 'points': 0}
                    }
                    
                    for row in rows:
                        category = row[0]
                        stats[category] = {
                            'count': row[1],
                            'points': row[2]
                        }
                    
                    return stats
                    
        except Exception as e:
            print(f"❌ 팀 카테고리 통계 조회 실패: {e}")
            return {}

    async def check_daily_all_clear_bonus(
        self,
        team_id: str,
        completion_date: str = None
    ) -> tuple[bool, int]:
        """특정 날짜에 팀이 모든 일일 퀘스트를 완료했는지 확인
        
        Args:
            completion_date: 'YYYY-MM-DD' 형식, None이면 오늘
        
        Returns:
            (전체완료여부, 보너스점수)
        """
        try:
            from datetime import datetime
            
            if not completion_date:
                completion_date = datetime.now().strftime('%Y-%m-%d')
            
            async with aiosqlite.connect(self.db_path) as db:
                # 해당 서버의 일일 퀘스트 총 개수
                async with db.execute('''
                    SELECT COUNT(*) 
                    FROM event_missions m
                    JOIN event_teams t ON m.guild_id = t.guild_id
                    WHERE t.team_id = ? AND m.category = 'daily' AND m.is_active = TRUE
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    total_daily = row[0] if row[0] else 0
                
                if total_daily == 0:
                    return False, 0
                
                # 해당 날짜에 팀이 완료한 일일 퀘스트 개수 (중복 제거)
                async with db.execute('''
                    SELECT COUNT(DISTINCT c.mission_id)
                    FROM event_mission_completions c
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.team_id = ? 
                    AND m.category = 'daily'
                    AND DATE(c.completed_at) = ?
                ''', (team_id, completion_date)) as cursor:
                    row = await cursor.fetchone()
                    completed_daily = row[0] if row[0] else 0
                
                # ✅ 전체 완료 시 보너스 (5점)
                if completed_daily >= total_daily:
                    return True, 5
                
                return False, 0
                
        except Exception as e:
            print(f"❌ 일일 전체 완료 보너스 체크 실패: {e}")
            return False, 0

    async def get_team_rankings(self, guild_id: str) -> list:
        """서버의 전체 팀 순위 (점수 순)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 오늘 날짜 계산 (오전 9시 기준)
                now = datetime.now()
                if now.hour < 9:
                    today = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                else:
                    today = now.strftime('%Y-%m-%d')
                
                async with db.execute('''
                    SELECT 
                        t.team_id,
                        t.team_name,
                        COALESCE(mission_scores.total_score, 0) as mission_score,
                        COALESCE(mission_scores.completed_missions, 0) as completed_missions,
                        COALESCE(members.member_count, 0) as member_count,
                        COALESCE(voice_scores.voice_score, 0) as voice_score
                    FROM event_teams t
                    LEFT JOIN (
                        SELECT 
                            team_id,
                            SUM(awarded_points) as total_score,
                            COUNT(DISTINCT mission_id) as completed_missions
                        FROM event_mission_completions
                        GROUP BY team_id
                    ) mission_scores ON t.team_id = mission_scores.team_id
                    LEFT JOIN (
                        SELECT 
                            team_id,
                            COUNT(DISTINCT user_id) as member_count
                        FROM event_team_members
                        GROUP BY team_id
                    ) members ON t.team_id = members.team_id
                    LEFT JOIN (
                        SELECT 
                            team_id,
                            total_score as voice_score
                        FROM voice_team_daily_scores
                        WHERE date = ?
                    ) voice_scores ON t.team_id = voice_scores.team_id
                    WHERE t.guild_id = ? AND t.is_active = TRUE
                ''', (today, guild_id)) as cursor:
                    rows = await cursor.fetchall()
                    
                    rankings = []
                    for row in rows:
                        mission_score = row[2]
                        voice_score = row[5]
                        total_score = mission_score + voice_score
                        
                        rankings.append({
                            'rank': 0,  # 나중에 정렬 후 순위 부여
                            'team_id': row[0],
                            'team_name': row[1],
                            'total_score': total_score,
                            'mission_score': mission_score,
                            'voice_score': voice_score,
                            'completed_missions': row[3],
                            'member_count': row[4]
                        })
                    
                    # 총 점수로 정렬
                    rankings.sort(key=lambda x: (x['total_score'], x['completed_missions'], x['team_name']), reverse=True)
                    
                    # 순위 부여
                    for rank, team_data in enumerate(rankings, 1):
                        team_data['rank'] = rank
                    
                    return rankings
                    
        except Exception as e:
            print(f"❌ 팀 순위 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def get_team_rank(self, team_id: str) -> dict:
        """특정 팀의 순위 정보"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 팀의 길드 ID 조회
                async with db.execute('''
                    SELECT guild_id FROM event_teams WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    guild_id = row[0]
                
                # 전체 순위 조회 (음성 점수 포함)
                rankings = await self.get_team_rankings(guild_id)
                
                # 해당 팀 찾기
                for team_rank in rankings:
                    if team_rank['team_id'] == team_id:
                        return {
                            'rank': team_rank['rank'],
                            'total_teams': len(rankings),
                            'team_name': team_rank['team_name'],
                            'total_score': team_rank['total_score'],
                            'mission_score': team_rank['mission_score'],
                            'voice_score': team_rank['voice_score'],
                            'completed_missions': team_rank['completed_missions']
                        }
                
                return None
                    
        except Exception as e:
            print(f"❌ 팀 순위 정보 조회 실패: {e}")
            return None

    async def get_event_overview(self, guild_id: str) -> dict:
        """이벤트 전체 현황 통계"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                overview = {}
                
                # 총 팀 수
                async with db.execute('''
                    SELECT COUNT(*) FROM event_teams
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    overview['total_teams'] = row[0] if row[0] else 0
                
                # 총 미션 수
                async with db.execute('''
                    SELECT COUNT(*) FROM event_missions
                    WHERE guild_id = ? AND is_active = TRUE
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    overview['total_missions'] = row[0] if row[0] else 0
                
                # 카테고리별 미션 수
                async with db.execute('''
                    SELECT category, COUNT(*) 
                    FROM event_missions
                    WHERE guild_id = ? AND is_active = TRUE
                    GROUP BY category
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    overview['missions_by_category'] = {
                        'daily': 0, 'online': 0, 'offline': 0, 'hidden': 0
                    }
                    for row in rows:
                        overview['missions_by_category'][row[0]] = row[1]
                
                # 총 미션 완료 횟수
                async with db.execute('''
                    SELECT COUNT(c.completion_id)
                    FROM event_mission_completions c
                    WHERE c.team_id IN (
                        SELECT team_id FROM event_teams WHERE guild_id = ?
                    )
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    overview['total_completions'] = row[0] if row[0] else 0
                
                # 총 부여된 점수
                async with db.execute('''
                    SELECT COALESCE(SUM(c.awarded_points), 0)
                    FROM event_mission_completions c
                    WHERE c.team_id IN (
                        SELECT team_id FROM event_teams WHERE guild_id = ?
                    )
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    overview['total_points_awarded'] = row[0] if row[0] else 0
                
                # ✅ 가장 많이 완료된 미션 TOP 3 (수정)
                async with db.execute('''
                    SELECT 
                        m.mission_name,
                        m.category,
                        COUNT(c.completion_id) as completion_count
                    FROM event_mission_completions c
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.team_id IN (
                        SELECT team_id FROM event_teams WHERE guild_id = ?
                    )
                    GROUP BY c.mission_id
                    ORDER BY completion_count DESC
                    LIMIT 3
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    overview['popular_missions'] = []
                    for row in rows:
                        overview['popular_missions'].append({
                            'mission_name': row[0],
                            'category': row[1],
                            'completion_count': row[2]
                        })
                
                # 평균 팀 점수
                if overview['total_teams'] > 0:
                    overview['avg_team_score'] = round(
                        overview['total_points_awarded'] / overview['total_teams'],
                        1
                    )
                else:
                    overview['avg_team_score'] = 0
                
                return overview
                    
        except Exception as e:
            print(f"❌ 이벤트 전체 통계 조회 실패: {e}")
            import traceback
            traceback.print_exc()
            return {}

    async def get_team_completion_rate(self, team_id: str) -> dict:
        """팀의 미션 완료율 (카테고리별)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 팀의 길드 ID 조회
                async with db.execute('''
                    SELECT guild_id FROM event_teams WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    guild_id = row[0]
                
                completion_rates = {}
                
                for category in ['daily', 'online', 'offline', 'hidden']:
                    # 해당 카테고리의 전체 미션 수
                    async with db.execute('''
                        SELECT COUNT(*) 
                        FROM event_missions
                        WHERE guild_id = ? AND category = ? AND is_active = TRUE
                    ''', (guild_id, category)) as cursor:
                        row = await cursor.fetchone()
                        total_missions = row[0] if row[0] else 0
                    
                    # 팀이 완료한 미션 수 (중복 제외)
                    async with db.execute('''
                        SELECT COUNT(DISTINCT c.mission_id)
                        FROM event_mission_completions c
                        JOIN event_missions m ON c.mission_id = m.mission_id
                        WHERE c.team_id = ? AND m.category = ?
                    ''', (team_id, category)) as cursor:
                        row = await cursor.fetchone()
                        completed_missions = row[0] if row[0] else 0
                    
                    # 완료율 계산
                    if total_missions > 0:
                        rate = round((completed_missions / total_missions) * 100, 1)
                    else:
                        rate = 0
                    
                    completion_rates[category] = {
                        'total': total_missions,
                        'completed': completed_missions,
                        'rate': rate
                    }
                
                return completion_rates
                    
        except Exception as e:
            print(f"❌ 팀 완료율 계산 실패: {e}")
            return {}

    async def get_recent_event_activities(
        self, 
        guild_id: str,
        limit: int = 10
    ) -> list:
        """서버의 최근 미션 완료 활동"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        t.team_name,
                        m.mission_name,
                        m.category,
                        c.awarded_points,
                        c.participants_count,
                        c.completed_at
                    FROM event_mission_completions c
                    JOIN event_teams t ON c.team_id = t.team_id
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE t.guild_id = ?
                    ORDER BY c.completed_at DESC
                    LIMIT ?
                ''', (guild_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    activities = []
                    for row in rows:
                        activities.append({
                            'team_name': row[0],
                            'mission_name': row[1],
                            'category': row[2],
                            'awarded_points': row[3],
                            'participants_count': row[4],
                            'completed_at': row[5]
                        })
                    
                    return activities
                    
        except Exception as e:
            print(f"❌ 최근 활동 내역 조회 실패: {e}")
            return []

    async def check_daily_mission_completed(
        self, 
        team_id: str, 
        mission_id: str, 
        completion_date: str = None
    ) -> bool:
        """특정 날짜에 팀이 이미 해당 미션을 완료했는지 체크
        
        Args:
            team_id: 팀 ID
            mission_id: 미션 ID
            completion_date: 'YYYY-MM-DD' 형식, None이면 오늘
        
        Returns:
            True: 이미 완료함
            False: 아직 완료 안 함
        """
        try:
            from datetime import datetime
            
            if not completion_date:
                completion_date = datetime.now().strftime('%Y-%m-%d')
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT COUNT(*) 
                    FROM event_mission_completions
                    WHERE team_id = ? 
                    AND mission_id = ?
                    AND DATE(completed_at) = ?
                ''', (team_id, mission_id, completion_date)) as cursor:
                    row = await cursor.fetchone()
                    count = row[0] if row[0] else 0
                    
                    return count > 0  # 1개 이상이면 True (이미 완료)
                    
        except Exception as e:
            print(f"❌ 일일 미션 완료 체크 실패: {e}")
            return False  # 에러 시 False 반환 (진행 허용)

    async def check_daily_all_clear_bonus_already_given(
        self,
        team_id: str,
        completion_date: str = None
    ) -> bool:
        """오늘 이미 올클리어 보너스를 받았는지 체크
        
        Returns:
            True: 이미 받음
            False: 아직 안 받음
        """
        try:
            from datetime import datetime
            
            if not completion_date:
                completion_date = datetime.now().strftime('%Y-%m-%d')
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT COUNT(*) 
                    FROM event_mission_completions
                    WHERE team_id = ? 
                    AND mission_id = 'daily_all_clear_bonus'
                    AND DATE(completed_at) = ?
                ''', (team_id, completion_date)) as cursor:
                    row = await cursor.fetchone()
                    count = row[0] if row[0] else 0
                    
                    return count > 0  # 이미 받았으면 True
                    
        except Exception as e:
            print(f"❌ 올클리어 보너스 중복 체크 실패: {e}")
            return True  # 에러 시 중복 방지를 위해 True 반환

    async def debug_team_completions(self, team_id: str) -> dict:
        """팀의 모든 완료 기록 디버깅용 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 전체 완료 기록
                async with db.execute('''
                    SELECT 
                        c.completion_id,
                        c.mission_id,
                        m.mission_name,
                        m.category,
                        c.awarded_points,
                        c.completed_at,
                        DATE(c.completed_at) as completion_date
                    FROM event_mission_completions c
                    LEFT JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.team_id = ?
                    ORDER BY c.completed_at DESC
                ''', (team_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    completions = []
                    total_points = 0
                    
                    for row in rows:
                        completion = {
                            'completion_id': row[0],
                            'mission_id': row[1],
                            'mission_name': row[2] or '(보너스)',
                            'category': row[3] or 'bonus',
                            'awarded_points': row[4],
                            'completed_at': row[5],
                            'completion_date': row[6]
                        }
                        completions.append(completion)
                        total_points += row[4]
                    
                    return {
                        'team_id': team_id,
                        'total_completions': len(completions),
                        'total_points': total_points,
                        'completions': completions
                    }
                    
        except Exception as e:
            print(f"❌ 디버그 조회 실패: {e}")
            return {}

    async def set_event_announcement_channel(
        self,
        guild_id: str,
        channel_id: str
    ) -> tuple[bool, str]:
        """이벤트 공지 채널 설정"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # UPSERT (있으면 업데이트, 없으면 삽입)
                await db.execute('''
                    INSERT INTO event_announcement_channels (guild_id, channel_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id) 
                    DO UPDATE SET 
                        channel_id = excluded.channel_id,
                        updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, channel_id))
                
                await db.commit()
                print(f"✅ 이벤트 공지 채널 설정: {guild_id} -> {channel_id}")
                return True, "공지 채널이 설정되었습니다"
                
        except Exception as e:
            print(f"❌ 공지 채널 설정 실패: {e}")
            return False, str(e)

    async def get_event_announcement_channel(self, guild_id: str) -> str:
        """이벤트 공지 채널 조회
        
        Returns:
            channel_id 또는 None
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT channel_id 
                    FROM event_announcement_channels
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else None
                    
        except Exception as e:
            print(f"❌ 공지 채널 조회 실패: {e}")
            return None

    async def remove_event_announcement_channel(self, guild_id: str) -> tuple[bool, str]:
        """이벤트 공지 채널 해제"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                cursor = await db.execute('''
                    DELETE FROM event_announcement_channels
                    WHERE guild_id = ?
                ''', (guild_id,))
                
                await db.commit()
                
                if cursor.rowcount == 0:
                    return False, "설정된 공지 채널이 없습니다"
                
                print(f"✅ 이벤트 공지 채널 해제: {guild_id}")
                return True, "공지 채널 설정이 해제되었습니다"
                
        except Exception as e:
            print(f"❌ 공지 채널 해제 실패: {e}")
            return False, str(e)

    async def create_event_voice_session(
        self,
        guild_id: str,
        channel_id: str,
        team_id: str,
        member_count: int
    ) -> tuple[bool, str]:
        """음성 채널 세션 생성
        
        Returns:
            (성공여부, session_id 또는 에러메시지)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                session_id = self.generate_uuid()
                
                await db.execute('''
                    INSERT INTO event_voice_sessions 
                    (session_id, guild_id, channel_id, team_id, member_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, guild_id, channel_id, team_id, member_count))
                
                await db.commit()
                return True, session_id
                
        except Exception as e:
            print(f"❌ 음성 세션 생성 실패: {e}")
            return False, str(e)
    
    async def get_active_voice_session(
        self,
        guild_id: str,
        channel_id: str,
        team_id: str
    ) -> dict:
        """활성 음성 채널 세션 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        session_id,
                        member_count,
                        session_start,
                        last_checked,
                        hours_completed,
                        points_awarded
                    FROM event_voice_sessions
                    WHERE guild_id = ? 
                        AND channel_id = ? 
                        AND team_id = ?
                        AND is_active = TRUE
                    ORDER BY session_start DESC
                    LIMIT 1
                ''', (guild_id, channel_id, team_id)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'session_id': row[0],
                            'member_count': row[1],
                            'session_start': row[2],
                            'last_checked': row[3],
                            'hours_completed': row[4],
                            'points_awarded': row[5]
                        }
                    return None
                    
        except Exception as e:
            print(f"❌ 활성 세션 조회 실패: {e}")
            return None
    
    async def update_voice_session(
        self,
        session_id: str,
        member_count: int = None,
        hours_completed: int = None,
        points_awarded: int = None
    ) -> bool:
        """음성 채널 세션 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                updates = ["last_checked = CURRENT_TIMESTAMP"]
                params = []
                
                if member_count is not None:
                    updates.append("member_count = ?")
                    params.append(member_count)
                
                if hours_completed is not None:
                    updates.append("hours_completed = ?")
                    params.append(hours_completed)
                
                if points_awarded is not None:
                    updates.append("points_awarded = ?")
                    params.append(points_awarded)
                
                params.append(session_id)
                
                query = f'''
                    UPDATE event_voice_sessions
                    SET {", ".join(updates)}
                    WHERE session_id = ?
                '''
                
                await db.execute(query, params)
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 세션 업데이트 실패: {e}")
            return False
    
    async def end_voice_session(self, session_id: str) -> bool:
        """음성 채널 세션 종료"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE event_voice_sessions
                    SET is_active = FALSE,
                        session_end = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                ''', (session_id,))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 세션 종료 실패: {e}")
            return False
    
    async def log_voice_activity_points(
        self,
        session_id: str,
        team_id: str,
        points_awarded: int,
        member_count: int,
        hours_at_award: int,
        reason: str = None
    ) -> bool:
        """음성 활동 점수 부여 로그 기록"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                log_id = self.generate_uuid()
                
                await db.execute('''
                    INSERT INTO event_voice_activity_log
                    (log_id, session_id, team_id, points_awarded, 
                     member_count, hours_at_award, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (log_id, session_id, team_id, points_awarded, 
                      member_count, hours_at_award, reason))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 음성 활동 로그 기록 실패: {e}")
            return False
    
    async def get_all_active_voice_sessions(self, guild_id: str) -> list:
        """서버의 모든 활성 음성 세션 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        vs.session_id,
                        vs.channel_id,
                        vs.team_id,
                        t.team_name,
                        vs.member_count,
                        vs.session_start,
                        vs.last_checked,
                        vs.hours_completed,
                        vs.points_awarded
                    FROM event_voice_sessions vs
                    JOIN event_teams t ON vs.team_id = t.team_id
                    WHERE vs.guild_id = ? AND vs.is_active = TRUE
                    ORDER BY vs.session_start
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    sessions = []
                    for row in rows:
                        sessions.append({
                            'session_id': row[0],
                            'channel_id': row[1],
                            'team_id': row[2],
                            'team_name': row[3],
                            'member_count': row[4],
                            'session_start': row[5],
                            'last_checked': row[6],
                            'hours_completed': row[7],
                            'points_awarded': row[8]
                        })
                    
                    return sessions
                    
        except Exception as e:
            print(f"❌ 활성 세션 목록 조회 실패: {e}")
            return []
    
    async def get_team_voice_activity_stats(
        self,
        team_id: str
    ) -> dict:
        """팀의 음성 활동 통계 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 전체 통계
                async with db.execute('''
                    SELECT 
                        COUNT(*) as total_sessions,
                        SUM(points_awarded) as total_points,
                        SUM(hours_completed) as total_hours
                    FROM event_voice_sessions
                    WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'total_sessions': row[0] or 0,
                            'total_points': row[1] or 0,
                            'total_hours': row[2] or 0
                        }
                    return {
                        'total_sessions': 0,
                        'total_points': 0,
                        'total_hours': 0
                    }
                    
        except Exception as e:
            print(f"❌ 음성 활동 통계 조회 실패: {e}")
            return {
                'total_sessions': 0,
                'total_points': 0,
                'total_hours': 0
            }
    
    async def get_user_team(self, guild_id: str, user_id: str) -> dict:
        """유저가 속한 팀 정보 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT t.team_id, t.team_name, t.guild_id
                    FROM event_teams t
                    JOIN event_team_members m ON t.team_id = m.team_id
                    WHERE t.guild_id = ? 
                        AND m.user_id = ? 
                        AND t.is_active = TRUE
                    LIMIT 1
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'team_id': row[0],
                            'team_name': row[1],
                            'guild_id': row[2]
                        }
                    return None
                    
        except Exception as e:
            print(f"❌ 유저 팀 정보 조회 실패: {e}")
            return None
    
    async def get_team_members(self, team_id: str) -> list:
        """팀의 모든 멤버 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT user_id, username, joined_at
                    FROM event_team_members
                    WHERE team_id = ?
                    ORDER BY joined_at
                ''', (team_id,)) as cursor:
                    rows = await cursor.fetchall()
                    
                    members = []
                    for row in rows:
                        members.append({
                            'user_id': row[0],
                            'username': row[1],
                            'joined_at': row[2]
                        })
                    
                    return members
                    
        except Exception as e:
            print(f"❌ 팀원 목록 조회 실패: {e}")
            return []
    
    async def get_team_by_id(self, team_id: str) -> dict:
        """팀 ID로 팀 정보 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        team_id,
                        guild_id,
                        team_name,
                        created_by,
                        created_at,
                        is_active
                    FROM event_teams
                    WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return {
                            'team_id': row[0],
                            'guild_id': row[1],
                            'team_name': row[2],
                            'created_by': row[3],
                            'created_at': row[4],
                            'is_active': row[5]
                        }
                    return None
                    
        except Exception as e:
            print(f"❌ 팀 정보 조회 실패: {e}")
            return None
        
    async def get_voice_team_daily_score(self, team_id: str, date: str) -> int:
        """팀의 특정 날짜 음성 활동 점수 조회
        
        Args:
            team_id: 팀 ID
            date: 날짜 (YYYY-MM-DD 형식)
        
        Returns:
            해당 날짜의 총 점수
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT total_score 
                    FROM voice_team_daily_scores
                    WHERE team_id = ? AND date = ?
                ''', (team_id, date)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
        except Exception as e:
            print(f"❌ 음성 팀 일일 점수 조회 실패: {e}")
            return 0
    
    async def add_voice_team_score(
        self, 
        team_id: str, 
        date: str, 
        points: int, 
        session_data: dict
    ) -> bool:
        """팀의 음성 활동 점수 추가
        
        Args:
            team_id: 팀 ID
            date: 날짜 (YYYY-MM-DD 형식)
            points: 추가할 점수
            session_data: 세션 정보 딕셔너리
        
        Returns:
            성공 여부
        """
        try:
            import json
            
            async with aiosqlite.connect(self.db_path) as db:
                # 기존 레코드 확인
                async with db.execute('''
                    SELECT total_score, sessions
                    FROM voice_team_daily_scores
                    WHERE team_id = ? AND date = ?
                ''', (team_id, date)) as cursor:
                    row = await cursor.fetchone()
                
                if row:
                    # 기존 레코드 업데이트
                    current_score = row[0]
                    sessions_json = row[1]
                    
                    # 세션 목록 파싱
                    try:
                        sessions = json.loads(sessions_json) if sessions_json else []
                    except:
                        sessions = []
                    
                    # 새 세션 추가
                    sessions.append(session_data)
                    
                    # 업데이트
                    await db.execute('''
                        UPDATE voice_team_daily_scores
                        SET total_score = ?,
                            sessions = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE team_id = ? AND date = ?
                    ''', (current_score + points, json.dumps(sessions, ensure_ascii=False), team_id, date))
                else:
                    # 새 레코드 생성
                    sessions = [session_data]
                    await db.execute('''
                        INSERT INTO voice_team_daily_scores (team_id, date, total_score, sessions)
                        VALUES (?, ?, ?, ?)
                    ''', (team_id, date, points, json.dumps(sessions, ensure_ascii=False)))
                
                await db.commit()
                return True
                
        except Exception as e:
            print(f"❌ 음성 팀 점수 추가 실패: {e}")
            return False
    
    async def get_event_team_member_ids(self, team_id: str) -> set:
        """팀원들의 user_id 세트 반환
        
        Args:
            team_id: 팀 ID
        
        Returns:
            user_id들의 set
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT user_id
                    FROM event_team_members
                    WHERE team_id = ?
                ''', (team_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return {row[0] for row in rows}
        except Exception as e:
            print(f"❌ 팀원 ID 목록 조회 실패: {e}")
            return set()

    async def get_team_today_voice_score(self, team_id: str) -> dict:
        """팀의 오늘 음성 활동 점수 상세 정보
        
        Returns:
            {
                'today_score': int,
                'max_score': int,
                'remaining': int,
                'session_count': int,
                'date': str
            }
        """
        try:
            from datetime import datetime, timedelta
            
            # 오늘 날짜 계산 (오전 9시 기준)
            now = datetime.now()
            if now.hour < 9:
                today = now - timedelta(days=1)
            else:
                today = now
            date_str = today.strftime('%Y-%m-%d')
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT total_score, sessions
                    FROM voice_team_daily_scores
                    WHERE team_id = ? AND date = ?
                ''', (team_id, date_str)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        import json
                        today_score = row[0]
                        sessions = json.loads(row[1]) if row[1] else []
                        
                        return {
                            'today_score': today_score,
                            'max_score': 10,
                            'remaining': max(0, 10 - today_score),
                            'session_count': len(sessions),
                            'date': date_str,
                            'sessions': sessions
                        }
                    else:
                        return {
                            'today_score': 0,
                            'max_score': 10,
                            'remaining': 10,
                            'session_count': 0,
                            'date': date_str,
                            'sessions': []
                        }
                        
        except Exception as e:
            print(f"❌ 오늘 음성 점수 조회 실패: {e}")
            return {
                'today_score': 0,
                'max_score': 10,
                'remaining': 10,
                'session_count': 0,
                'date': '',
                'sessions': []
            }

    async def save_active_voice_session(
        self,
        team_id: str,
        team_name: str,
        guild_id: str,
        channel_id: str,
        members: set,
        start_time: str,
        last_check_time: str,
        hours_awarded: int,
        is_bonus_mode: bool,
        bonus_start_time: Optional[str],
        member_count: int,
        channel_history: str
    ) -> bool:
        try:
            members_json = json.dumps(list(members))
            
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT OR REPLACE INTO active_voice_sessions (
                        team_id, team_name, guild_id, channel_id,
                        members, start_time, last_check_time, hours_awarded,
                        is_bonus_mode, bonus_start_time, member_count,
                        channel_history, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    team_id, team_name, guild_id, channel_id,
                    members_json, start_time, last_check_time, hours_awarded,
                    is_bonus_mode, bonus_start_time, member_count,
                    channel_history
                ))
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ 활성 세션 저장 실패: {e}", exc_info=True)
            return False

    async def load_active_voice_sessions(self) -> List[Dict]:
        """활성 음성 세션 전체 로드 (봇 시작 시)
        
        Returns:
            세션 정보 딕셔너리 리스트
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        team_id, team_name, guild_id, channel_id,
                        members, start_time, last_check_time, hours_awarded,
                        is_bonus_mode, bonus_start_time, member_count
                    FROM active_voice_sessions
                ''') as cursor:
                    rows = await cursor.fetchall()
                    
                    sessions = []
                    for row in rows:
                        sessions.append({
                            'team_id': row[0],
                            'team_name': row[1],
                            'guild_id': row[2],
                            'channel_id': row[3],
                            'members': set(json.loads(row[4])),
                            'start_time': row[5],
                            'last_check_time': row[6],
                            'hours_awarded': row[7],
                            'is_bonus_mode': bool(row[8]),
                            'bonus_start_time': row[9],
                            'member_count': row[10]
                        })
                    
                    return sessions
                    
        except Exception as e:
            logger.error(f"❌ 활성 세션 로드 실패: {e}", exc_info=True)
            return []
    
    async def get_all_active_voice_sessions(self) -> List[dict]:
        try:
            import json
            from datetime import datetime
            
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT team_id, team_name, guild_id, channel_id, members,
                        start_time, last_check_time, hours_awarded,
                        is_bonus_mode, bonus_start_time, member_count,
                        channel_history
                    FROM active_voice_sessions
                ''') as cursor:
                    rows = await cursor.fetchall()
                    
                    sessions = []
                    for row in rows:
                        sessions.append({
                            'team_id': row[0],
                            'team_name': row[1],
                            'guild_id': row[2],
                            'channel_id': row[3],
                            'members': set(json.loads(row[4])),
                            'start_time': datetime.fromisoformat(row[5]),
                            'last_check_time': datetime.fromisoformat(row[6]),
                            'hours_awarded': row[7],
                            'is_bonus_mode': bool(row[8]),
                            'bonus_start_time': datetime.fromisoformat(row[9]) if row[9] else None,
                            'member_count': row[10],
                            'channel_history': row[11]  # JSON string
                        })
                    
                    return sessions
                    
        except Exception as e:
            logger.error(f"❌ 활성 세션 목록 조회 실패: {e}", exc_info=True)
            return []
    
    async def delete_active_voice_session(self, team_id: str) -> bool:
        """활성 음성 세션 삭제 (세션 종료 시)
        
        Args:
            team_id: 팀 ID
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    DELETE FROM active_voice_sessions
                    WHERE team_id = ?
                ''', (team_id,))
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ 활성 세션 삭제 실패: {e}", exc_info=True)
            return False
    
    async def clear_all_active_voice_sessions(self) -> bool:
        """모든 활성 음성 세션 삭제 (초기화용)"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('DELETE FROM active_voice_sessions')
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ 활성 세션 전체 삭제 실패: {e}", exc_info=True)
            return False

    async def cleanup_stale_voice_sessions(self, max_age_hours: int = 24) -> int:
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 24시간 이상 업데이트되지 않은 세션 삭제
                result = await db.execute('''
                    DELETE FROM active_voice_sessions
                    WHERE datetime(updated_at) < datetime('now', '-' || ? || ' hours')
                ''', (max_age_hours,))
                await db.commit()
                
                deleted_count = result.rowcount
                if deleted_count > 0:
                    logger.info(f"🧹 {deleted_count}개의 오래된 세션 정리됨")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"❌ 오래된 세션 정리 실패: {e}", exc_info=True)
            return 0

    async def get_recent_mission_completions(
        self, 
        guild_id: str, 
        hours: int = 24, 
        limit: int = 25
    ) -> List[Dict]:
        """최근 미션 완료 내역 조회 (점수 취소용)
        
        Args:
            guild_id: 서버 ID
            hours: 최근 몇 시간 이내 (기본 24시간)
            limit: 최대 조회 개수 (Discord 제한 25개)
            
        Returns:
            [{
                'completion_id': str,
                'team_id': str,
                'team_name': str,
                'mission_id': str,
                'mission_name': str,
                'awarded_points': int,
                'participants_count': int,
                'completed_at': str,
                'completed_by': str,
                'completed_by_name': str,
                'notes': str
            }, ...]
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT 
                        c.completion_id,
                        c.team_id,
                        t.team_name,
                        c.mission_id,
                        m.mission_name,
                        c.awarded_points,
                        c.participants_count,
                        c.completed_at,
                        c.completed_by,
                        c.notes
                    FROM event_mission_completions c
                    JOIN event_teams t ON c.team_id = t.team_id
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE t.guild_id = ?
                        AND datetime(c.completed_at) >= datetime('now', '-' || ? || ' hours')
                    ORDER BY c.completed_at DESC
                    LIMIT ?
                ''', (guild_id, hours, limit)) as cursor:
                    rows = await cursor.fetchall()
                    
                    completions = []
                    for row in rows:
                        completions.append({
                            'completion_id': row[0],
                            'team_id': row[1],
                            'team_name': row[2],
                            'mission_id': row[3],
                            'mission_name': row[4],
                            'awarded_points': row[5],
                            'participants_count': row[6],
                            'completed_at': row[7],
                            'completed_by': row[8],
                            'notes': row[9]
                        })
                    
                    return completions
                    
        except Exception as e:
            logger.error(f"❌ 최근 미션 완료 내역 조회 실패: {e}", exc_info=True)
            return []

    async def cancel_mission_completion(
        self, 
        completion_id: str,
        cancelled_by: str,
        reason: str = "관리자 취소"
    ) -> Tuple[bool, str, Optional[Dict]]:
        """미션 완료 취소 및 점수 롤백
        
        Args:
            completion_id: 완료 기록 ID
            cancelled_by: 취소한 관리자 ID
            reason: 취소 사유
            
        Returns:
            (성공여부, 메시지, 취소된 내역 정보)
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 1. 완료 내역 조회
                async with db.execute('''
                    SELECT 
                        c.completion_id,
                        c.team_id,
                        t.team_name,
                        c.mission_id,
                        m.mission_name,
                        c.awarded_points,
                        c.participants_count,
                        c.completed_at,
                        c.completed_by
                    FROM event_mission_completions c
                    JOIN event_teams t ON c.team_id = t.team_id
                    JOIN event_missions m ON c.mission_id = m.mission_id
                    WHERE c.completion_id = ?
                ''', (completion_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if not row:
                        return False, "해당 완료 기록을 찾을 수 없습니다.", None
                    
                    completion_info = {
                        'completion_id': row[0],
                        'team_id': row[1],
                        'team_name': row[2],
                        'mission_id': row[3],
                        'mission_name': row[4],
                        'awarded_points': row[5],
                        'participants_count': row[6],
                        'completed_at': row[7],
                        'completed_by': row[8]
                    }
                
                # 2. 완료 기록 삭제
                await db.execute('''
                    DELETE FROM event_mission_completions
                    WHERE completion_id = ?
                ''', (completion_id,))
                
                # 3. 팀 점수 롤백 (음수로 기록)
                await db.execute('''
                    INSERT INTO event_mission_completions (
                        completion_id, team_id, mission_id, participants_count,
                        awarded_points, completed_by, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.generate_uuid(),
                    completion_info['team_id'],
                    completion_info['mission_id'],
                    0,  # 취소 기록이므로 참여자 0
                    -completion_info['awarded_points'],  # 음수로 기록
                    cancelled_by,
                    f"[점수 취소] {reason} (원본: {completion_id})"
                ))
                
                await db.commit()
                
                logger.info(
                    f"✅ 미션 완료 취소: {completion_info['team_name']} | "
                    f"{completion_info['mission_name']} | "
                    f"-{completion_info['awarded_points']}점"
                )
                
                return True, "점수 취소 완료", completion_info
                
        except Exception as e:
            logger.error(f"❌ 미션 완료 취소 실패: {e}", exc_info=True)
            return False, f"취소 처리 중 오류 발생: {str(e)}", None

    async def migrate_active_voice_sessions_table(self):
        """active_voice_sessions 테이블 마이그레이션
        
        - session_key 제거
        - team_id를 PRIMARY KEY로 변경
        - channel_history 필드 추가
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # WAL 모드 활성화
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 1. 기존 데이터 백업
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS active_voice_sessions_backup AS 
                    SELECT * FROM active_voice_sessions
                ''')
                print("✅ 1단계: 기존 데이터 백업 완료")
                
                # 2. 기존 테이블 삭제
                await db.execute('DROP TABLE IF EXISTS active_voice_sessions')
                print("✅ 2단계: 기존 테이블 삭제 완료")
                
                # 3. 새 스키마로 테이블 재생성
                await db.execute('''
                    CREATE TABLE active_voice_sessions (
                        team_id TEXT PRIMARY KEY,
                        team_name TEXT NOT NULL,
                        guild_id TEXT NOT NULL,
                        channel_id TEXT NOT NULL,
                        members TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        last_check_time TEXT NOT NULL,
                        hours_awarded INTEGER DEFAULT 0,
                        is_bonus_mode BOOLEAN DEFAULT FALSE,
                        bonus_start_time TEXT,
                        member_count INTEGER NOT NULL,
                        channel_history TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (team_id) REFERENCES event_teams(team_id) ON DELETE CASCADE
                    )
                ''')
                print("✅ 3단계: 새 테이블 생성 완료")
                
                # 4. 데이터 복원 (team_id별 최신 데이터만)
                await db.execute('''
                    INSERT INTO active_voice_sessions (
                        team_id, team_name, guild_id, channel_id, members,
                        start_time, last_check_time, hours_awarded,
                        is_bonus_mode, bonus_start_time, member_count,
                        channel_history, created_at, updated_at
                    )
                    SELECT 
                        team_id,
                        team_name,
                        guild_id,
                        channel_id,
                        members,
                        start_time,
                        last_check_time,
                        hours_awarded,
                        is_bonus_mode,
                        bonus_start_time,
                        member_count,
                        '[]' as channel_history,
                        created_at,
                        updated_at
                    FROM active_voice_sessions_backup
                    WHERE rowid IN (
                        SELECT MAX(rowid)
                        FROM active_voice_sessions_backup
                        GROUP BY team_id
                    )
                ''')
                
                # 복원된 레코드 수 확인
                cursor = await db.execute('SELECT COUNT(*) FROM active_voice_sessions')
                row = await cursor.fetchone()
                restored_count = row[0] if row else 0
                print(f"✅ 4단계: 데이터 복원 완료 ({restored_count}개 레코드)")
                
                # 5. 백업 테이블 삭제
                await db.execute('DROP TABLE IF EXISTS active_voice_sessions_backup')
                print("✅ 5단계: 백업 테이블 삭제 완료")
                
                # 6. 인덱스 재생성
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_active_voice_sessions_team 
                    ON active_voice_sessions(team_id)
                ''')
                await db.execute('''
                    CREATE INDEX IF NOT EXISTS idx_active_voice_sessions_guild 
                    ON active_voice_sessions(guild_id)
                ''')
                print("✅ 6단계: 인덱스 재생성 완료")
                
                await db.commit()
                print("🎉 active_voice_sessions 테이블 마이그레이션 완료!")
                return True
                
        except Exception as e:
            print(f"❌ 테이블 마이그레이션 실패: {e}")
            import traceback
            traceback.print_exc()
            return False







