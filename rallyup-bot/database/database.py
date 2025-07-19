import aiosqlite
import json
from datetime import datetime
from typing import List, Optional, Tuple
from database.models import User, Match, Participant, UserMatchup
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
        
            await db.commit()

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