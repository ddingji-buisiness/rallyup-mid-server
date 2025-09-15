import aiosqlite
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from utils.time_utils import TimeUtils

import discord
from database.models import ClanScrim, ClanTeam, User, Match, Participant, UserMatchup
import uuid
import asyncio

class DatabaseManager:
    def __init__(self, db_path: str = "database/rallyup.db"):
        self.db_path = db_path
    
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
            await self.update_server_settings_for_auto_role()
            await self.create_bamboo_tables()

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
                    entry_method TEXT NOT NULL,
                    battle_tag TEXT NOT NULL,
                    main_position TEXT NOT NULL,
                    previous_season_tier TEXT NOT NULL,
                    current_season_tier TEXT NOT NULL,
                    highest_tier TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    UNIQUE(guild_id, user_id)
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
            
            # 인덱스 생성
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_guild ON server_admins(guild_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_server_admins_user ON server_admins(user_id)')
            
            await db.commit()
            
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
                    status TEXT NOT NULL CHECK (status IN ('joined', 'declined')),
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
        
            await db.commit()

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
            
            await db.commit()

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
            
    async def create_user_application(self, guild_id: str, user_id: str, username: str, 
                                    entry_method: str, battle_tag: str, main_position: str,
                                    previous_season_tier: str, current_season_tier: str, highest_tier: str) -> bool:
        """사용자 신청 생성 - 재신청 허용 (UPSERT 방식)"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                # 기존 레코드가 있으면 업데이트, 없으면 삽입
                await db.execute('''
                    INSERT INTO user_applications 
                    (guild_id, user_id, username, entry_method, battle_tag, main_position, 
                    previous_season_tier, current_season_tier, highest_tier, status, applied_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        username = excluded.username,
                        entry_method = excluded.entry_method,
                        battle_tag = excluded.battle_tag,
                        main_position = excluded.main_position,
                        previous_season_tier = excluded.previous_season_tier,
                        current_season_tier = excluded.current_season_tier,
                        highest_tier = excluded.highest_tier,
                        status = 'pending',
                        applied_at = CURRENT_TIMESTAMP,
                        reviewed_at = NULL,
                        reviewed_by = NULL,
                        admin_note = NULL
                ''', (guild_id, user_id, username, entry_method, battle_tag, main_position,
                    previous_season_tier, current_season_tier, highest_tier))
                
                await db.commit()
                return True
                
            except Exception as e:
                print(f"신청 생성/업데이트 오류: {e}")
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

    async def approve_user_application_with_nickname(self, guild_id: str, user_id: str, admin_id: str, 
                                                discord_member: discord.Member, admin_note: str = None) -> tuple[bool, str]:
        """유저 신청 승인 및 닉네임 자동 변경"""
        async with aiosqlite.connect(self.db_path, timeout=30.0) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            # 먼저 신청 정보 가져오기
            async with db.execute('''
                SELECT * FROM user_applications 
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
            
            # 기존 레코드가 있으면 UPDATE, 없으면 INSERT
            await db.execute('''
                INSERT INTO registered_users 
                (guild_id, user_id, username, entry_method, battle_tag, main_position, 
                previous_season_tier, current_season_tier, highest_tier, approved_by, is_active, registered_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    username = excluded.username,
                    entry_method = excluded.entry_method,
                    battle_tag = excluded.battle_tag,
                    main_position = excluded.main_position,
                    previous_season_tier = excluded.previous_season_tier,
                    current_season_tier = excluded.current_season_tier,
                    highest_tier = excluded.highest_tier,
                    approved_by = excluded.approved_by,
                    is_active = TRUE,
                    registered_at = CURRENT_TIMESTAMP
            ''', (application[1], application[2], application[3], application[4], 
                application[5], application[6], application[7], application[8], application[9], admin_id))
            
            await db.commit()
            
            # 닉네임 변경 시도 (배틀태그, 포지션, 현시즌티어 사용)
            nickname_result = await self._update_user_nickname(
                discord_member, 
                application[6],  # main_position
                application[8],  # current_season_tier  
                application[5]   # battle_tag
            )
            role_result = await self._update_user_roles_conditional(discord_member, guild_id)

            combined_result = f"{nickname_result}\n{role_result}"

            return True, combined_result

    async def _update_user_nickname(self, member: discord.Member, position: str, tier: str, battle_tag: str) -> str:
        """유저 닉네임 업데이트 (배틀태그 기반)"""
        try:
            # 포지션 축약 (복합 포지션 처리)
            position_short = self._shorten_position(position)
            
            # 새로운 닉네임 생성: 배틀태그 / 포지션 / 티어
            new_nickname = f"{battle_tag}/{position_short}/{tier}"
            
            # 32자 제한 (Discord 닉네임 길이 제한)
            if len(new_nickname) > 32:
                # 배틀태그에서 #태그 부분 제거해서 다시 시도
                battle_name = battle_tag.split('#')[0] if '#' in battle_tag else battle_tag
                new_nickname = f"{battle_name}/{position_short}/{tier}"
                
                if len(new_nickname) > 32:
                    # 그래도 길면 배틀태그를 더 줄임
                    max_battle_length = 32 - len(f"/{position_short}/{tier}")
                    if max_battle_length > 3:  # 최소 3자는 남겨둠
                        battle_name = battle_name[:max_battle_length]
                        new_nickname = f"{battle_name}/{position_short}/{tier}"
                    else:
                        # 그래도 길면 포지션만 표시
                        new_nickname = f"{battle_name[:15]}/{position_short}"
            
            await member.edit(nick=new_nickname)
            return f"닉네임이 '{new_nickname}'으로 변경되었습니다."
            
        except discord.Forbidden:
            return "닉네임 변경 권한이 부족합니다. (봇 권한 확인 필요)"
        except discord.HTTPException as e:
            return f"닉네임 변경 실패: {str(e)}"
        except Exception as e:
            return f"닉네임 변경 중 오류: {str(e)}"

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
                    SELECT user_id, username, battle_tag, main_position, 
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
                            'battle_tag': row[2],
                            'main_position': row[3],
                            'current_season_tier': row[4],
                            'registered_at': row[5],
                            'approved_by': row[6]
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

    async def update_server_settings_for_auto_role(self):
        """신규 유저 자동 역할 배정을 위한 server_settings 테이블 업데이트"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('PRAGMA journal_mode=WAL')
            
            try:
                # 새로운 컬럼들 추가
                await db.execute('''
                    ALTER TABLE server_settings 
                    ADD COLUMN new_member_role_id TEXT
                ''')
                print("✅ new_member_role_id 컬럼 추가됨")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("ℹ️ new_member_role_id 컬럼이 이미 존재함")
                else:
                    print(f"❌ new_member_role_id 컬럼 추가 실패: {e}")
            
            try:
                await db.execute('''
                    ALTER TABLE server_settings 
                    ADD COLUMN auto_assign_new_member BOOLEAN DEFAULT FALSE
                ''')
                print("✅ auto_assign_new_member 컬럼 추가됨")
            except Exception as e:
                if "duplicate column name" in str(e).lower():
                    print("ℹ️ auto_assign_new_member 컬럼이 이미 존재함")
                else:
                    print(f"❌ auto_assign_new_member 컬럼 추가 실패: {e}")
            
            await db.commit()
            print("🎯 신규 유저 자동 역할 배정 스키마 업데이트 완료")

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
                    SELECT guild_id FROM server_settings WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    existing = await cursor.fetchone()
                
                if existing:
                    # 업데이트
                    await db.execute('''
                        UPDATE server_settings 
                        SET recruitment_channel_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                    ''', (channel_id, guild_id))
                else:
                    # 신규 생성
                    await db.execute('''
                        INSERT INTO server_settings (guild_id, recruitment_channel_id)
                        VALUES (?, ?)
                    ''', (guild_id, channel_id))
                
                await db.commit()
                
            return True
            
        except Exception as e:
            print(f"❌ 공지 채널 설정 실패: {e}")
            return False

    async def get_recruitment_channel(self, guild_id: str) -> Optional[str]:
        """설정된 내전 공지 채널 ID 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute('''
                    SELECT recruitment_channel_id FROM server_settings 
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
        """매치 결과를 데이터베이스에 저장"""
        try:
            match_id = str(uuid.uuid4())
            
            async with aiosqlite.connect(self.db_path) as db:
                # 매치 기본 정보 저장
                await db.execute('''
                    INSERT INTO match_results (
                        id, recruitment_id, match_number, winning_team, 
                        created_by, guild_id, match_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id,
                    match_data['recruitment_id'],
                    match_data['match_number'],
                    match_data['winner'],
                    match_data['created_by'],
                    match_data['guild_id'],
                    datetime.now().isoformat()
                ))
                
                # 참가자별 세부 정보 저장
                for team_key in ['team_a', 'team_b']:
                    team_data = match_data[team_key]
                    positions = match_data[f'{team_key}_positions']
                    is_winning_team = (match_data['winner'] == team_key)
                    
                    for participant in team_data:
                        user_id = participant['user_id']
                        position = positions[user_id]
                        
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
            print(f"매치 저장 실패: {e}")
            raise

    async def update_user_statistics(self, guild_id: str, match_results: List[Dict]):
        """여러 매치 결과를 기반으로 사용자 통계 업데이트"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                for match_data in match_results:
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
                
                await db.commit()
                
        except Exception as e:
            print(f"통계 업데이트 실패: {e}")
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

    async def get_server_rankings(self, guild_id: str, sort_by: str = 'winrate', 
                                position: str = 'all', min_games: int = 5) -> List[Dict]:
        """서버 내 사용자 랭킹 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 정렬 기준에 따른 쿼리 구성
                if sort_by == 'winrate':
                    order_clause = 'ORDER BY winrate DESC, total_games DESC'
                elif sort_by == 'games':
                    order_clause = 'ORDER BY total_games DESC'
                elif sort_by == 'wins':
                    order_clause = 'ORDER BY total_wins DESC'
                else:
                    order_clause = 'ORDER BY winrate DESC'
                
                # 포지션별 필터링
                if position != 'all':
                    position_filter = {
                        'tank': 'AND tank_games >= ?',
                        'dps': 'AND dps_games >= ?', 
                        'support': 'AND support_games >= ?'
                    }.get(position, '')
                else:
                    position_filter = ''
                
                query = f'''
                    SELECT us.user_id, ua.username, us.total_games, us.total_wins,
                        CASE WHEN us.total_games > 0 
                                THEN ROUND(us.total_wins * 100.0 / us.total_games, 1)
                                ELSE 0 END as winrate,
                        ua.current_season_tier
                    FROM user_statistics us
                    JOIN user_applications ua ON us.user_id = ua.user_id
                    WHERE us.guild_id = ? AND us.total_games >= ?
                    {position_filter}
                    {order_clause}
                    LIMIT 50
                '''
                
                params = [guild_id, min_games]
                if position != 'all':
                    params.append(min_games)
                
                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'user_id': row[0],
                            'username': row[1],
                            'total_games': row[2],
                            'wins': row[3],
                            'winrate': row[4],
                            'tier': row[5]
                        }
                        for row in rows
                    ]
                    
        except Exception as e:
            print(f"랭킹 조회 실패: {e}")
            return []

    async def get_user_server_rank(self, user_id: str, guild_id: str) -> Dict:
        """특정 사용자의 서버 내 순위 조회"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 전체 랭킹에서 해당 사용자 순위 찾기
                async with db.execute('''
                    WITH ranked_users AS (
                        SELECT user_id,
                            ROW_NUMBER() OVER (
                                ORDER BY 
                                    CASE WHEN total_games > 0 
                                            THEN total_wins * 100.0 / total_games 
                                            ELSE 0 END DESC,
                                    total_games DESC
                            ) as rank
                        FROM user_statistics
                        WHERE guild_id = ? AND total_games >= 5
                    ),
                    user_stats AS (
                        SELECT COUNT(*) as total_users
                        FROM user_statistics
                        WHERE guild_id = ? AND total_games >= 5
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
                        SUM(CASE WHEN mp1.won = 1 THEN 1 ELSE 0 END) as user1_wins,
                        SUM(CASE WHEN mp2.won = 1 THEN 1 ELSE 0 END) as user2_wins,
                        COUNT(*) as total_matches
                    FROM match_participants mp1
                    JOIN match_participants mp2 ON mp1.match_id = mp2.match_id
                    JOIN match_results mr ON mp1.match_id = mr.id
                    WHERE mp1.user_id = ? AND mp2.user_id = ? 
                        AND mp1.user_id != mp2.user_id
                        AND mr.guild_id = ?
                ''', (user1_id, user2_id, guild_id)) as cursor:
                    result = await cursor.fetchone()
                    
                    if result and result[2] > 0:
                        return {
                            'wins': result[0] or 0,
                            'losses': result[1] or 0,
                            'total_matches': result[2]
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