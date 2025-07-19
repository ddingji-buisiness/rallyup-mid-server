from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
import uuid

@dataclass
class User:
    discord_id: str
    username: str
    total_games: int = 0
    total_wins: int = 0
    tank_games: int = 0
    tank_wins: int = 0
    dps_games: int = 0
    dps_wins: int = 0
    support_games: int = 0
    support_wins: int = 0
    score: int = 1000  # 초기 점수
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class Match:
    id: Optional[int] = None
    guild_id: str = ""
    match_uuid: str = ""  
    team1_channel: str = ""  
    team2_channel: str = ""  
    winning_team: int = 0 
    has_position_data: bool = False  
    created_at: Optional[datetime] = None

@dataclass
class Participant:
    id: Optional[int] = None
    match_id: int = 0
    user_id: str = ""
    username: str = ""
    team_num: int = 0  # 1 또는 2
    position_order: int = 0  # 1-5 (채널 내 순서)
    position: Optional[str] = None  # 탱/딜/힐 (nullable)
    won: bool = False
    created_at: Optional[datetime] = None

@dataclass
class UserMatchup:
    id: Optional[int] = None
    user1_id: str = ""
    user2_id: str = ""
    user1_position: Optional[str] = None
    user2_position: Optional[str] = None
    user1_wins: int = 0
    user2_wins: int = 0
    total_matches: int = 0
    last_match_date: Optional[datetime] = None

@dataclass
class ScrimSession:
    """내전 세션 데이터 모델"""
    id: Optional[int] = None
    guild_id: str = ""
    session_uuid: str = ""
    voice_channel: str = ""
    session_name: Optional[str] = None
    total_participants: int = 0
    session_status: str = "active"  # 'active', 'completed', 'cancelled'
    started_by: str = ""
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_matches: int = 0

@dataclass
class SessionParticipant:
    """세션 참여자 데이터 모델"""
    id: Optional[int] = None
    session_id: int = 0
    user_id: str = ""
    username: str = ""
    join_order: int = 0
    is_present: bool = True
    joined_at: Optional[datetime] = None

@dataclass
class TeammateCombination:
    """팀메이트 조합 데이터 모델"""
    id: Optional[int] = None
    match_id: int = 0
    user1_id: str = ""
    user2_id: str = ""
    user1_position: Optional[str] = None
    user2_position: Optional[str] = None
    won: bool = False
    team_num: int = 0  # 1 또는 2
    created_at: Optional[datetime] = None

@dataclass
class TeamComposition:
    """팀 구성 분석 데이터 모델 (향후 확장용)"""
    id: Optional[int] = None
    match_id: int = 0
    team_num: int = 0  # 1 또는 2
    composition_hash: str = ""  # 포지션 조합의 해시값 (예: "tank-dps-dps-support-support")
    won: bool = False
    created_at: Optional[datetime] = None

@dataclass
class PlaySession:
    """플레이 세션 추적 모델 (향후 확장용)"""
    id: Optional[int] = None
    user_id: str = ""
    session_start: Optional[datetime] = None
    session_end: Optional[datetime] = None
    total_matches: int = 0
    wins: int = 0
    performance_trend: Optional[str] = None  # "improving", "declining", "stable"
    created_at: Optional[datetime] = None

@dataclass
class PlayerMatchStats:
    """개인 경기별 세부 통계 모델"""
    id: Optional[int] = None
    match_id: int = 0
    user_id: str = ""
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    damage: int = 0
    healing: int = 0
    objective_time: int = 0  # 초 단위
    mvp_votes: int = 0
    created_at: Optional[datetime] = None

@dataclass
class TeammateAnalysis:
    """팀메이트 분석 결과"""
    teammate_name: str
    teammate_id: str
    total_matches: int
    wins: int
    winrate: float
    best_position_combo: Optional[str] = None

@dataclass
class RivalAnalysis:
    """라이벌 분석 결과"""
    opponent_name: str
    opponent_id: str
    my_wins: int
    opponent_wins: int
    total_matches: int
    my_winrate: float
    difficulty_level: str = ""  # "천적", "호구", "균형"

@dataclass
class PositionSynergy:
    """포지션 시너지 분석 결과"""
    my_position: str
    teammate_position: str
    total_matches: int
    wins: int
    winrate: float
    synergy_level: str = ""  # "최고", "좋음", "보통", "나쁨"

@dataclass
class TeamBalance:
    """팀 밸런스 분석 결과"""
    team1_members: List[str]
    team2_members: List[str]
    team1_avg_score: float
    team2_avg_score: float
    balance_difference: float
    predicted_winrate: float  # 팀1 기준 예상 승률
    balance_quality: str = ""  # "완벽", "좋음", "보통", "불균형"

@dataclass
class UserRanking:
    """사용자 랭킹 정보"""
    user_id: str
    username: str
    rank: int
    score: int
    total_games: int
    total_wins: int
    winrate: float
    rank_change: Optional[int] = None  # 이전 랭킹 대비 변화
    
@dataclass
class PositionRanking:
    """포지션별 랭킹 정보"""
    user_id: str
    username: str
    position: str
    rank: int
    position_games: int
    position_wins: int
    position_winrate: float

@dataclass
class SessionAnalysis:
    """세션 분석 결과"""
    session_id: int
    session_name: Optional[str]
    duration_minutes: int
    total_participants: int
    total_matches: int
    avg_match_interval: float  # 경기 간 평균 간격(분)
    participation_rate: float  # 세션 완주율
    mvp_participants: List[str]  # 가장 활발한 참여자들

@dataclass
class UserSessionStats:
    """사용자 세션 참여 통계"""
    user_id: str
    username: str
    total_sessions: int
    active_days: int
    avg_matches_per_session: float
    last_session_date: Optional[datetime]
    participation_rate: float  # 전체 세션 대비 참여율
    favorite_time_slot: str  # 가장 자주 참여하는 시간대

@dataclass
class SessionTimeAnalysis:
    """세션 시간대 분석"""
    hour: int
    session_count: int
    avg_participants: float
    avg_matches: float
    popularity_rank: int

@dataclass
class CommunityHealth:
    """커뮤니티 건강도 지표"""
    total_active_users: int
    new_users_this_month: int
    returning_users: int
    average_session_size: float
    most_active_time: str
    community_engagement_score: float  # 0-100 점수

@dataclass
class ServerStats:
    """서버 전체 통계"""
    total_users: int
    total_matches: int
    total_games: int
    most_popular_position: str
    average_score: float
    top_player: str
    most_active_period: str