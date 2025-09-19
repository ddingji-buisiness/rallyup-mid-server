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
    score: int = 1000

    # 띵지워들 
    wordle_points: int = 10000 
    daily_points_claimed: Optional[str] = None 

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class UserApplication:
    id: Optional[int] = None
    guild_id: str = ""
    user_id: str = ""
    username: str = ""
    entry_method: str = ""  # 유입경로
    battle_tag: str = ""  # 배틀태그 (새로 추가)
    main_position: str = ""  # 메인 포지션 (탱커/딜러/힐러/복합)
    previous_season_tier: str = ""  # 전시즌 티어
    current_season_tier: str = ""  # 현시즌 티어
    highest_tier: str = ""  # 최고 티어
    status: str = "pending"  # pending, approved, rejected
    applied_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None  # 승인/거절한 관리자 ID
    admin_note: Optional[str] = None  # 관리자 메모
    
@dataclass
class RegisteredUser:
    id: Optional[int] = None
    guild_id: str = ""
    user_id: str = ""
    username: str = ""
    entry_method: str = ""
    battle_tag: str = ""  # 배틀태그 (새로 추가)
    main_position: str = ""
    previous_season_tier: str = ""
    current_season_tier: str = ""
    highest_tier: str = ""
    approved_by: str = ""  # 승인한 관리자 ID
    registered_at: Optional[datetime] = None
    is_active: bool = True

@dataclass
class ServerAdmin:
    """서버 관리자 데이터 모델"""
    id: Optional[int] = None
    guild_id: str = ""
    user_id: str = ""
    username: str = ""
    added_by: str = ""  # 추가한 관리자의 user_id
    added_at: Optional[datetime] = None
    is_active: bool = True

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
    """팀 구성 분석 데이터 모델"""
    id: Optional[int] = None
    match_id: int = 0
    team_num: int = 0  # 1 또는 2
    composition_hash: str = ""  # 포지션 조합의 해시값 (예: "tank-dps-dps-support-support")
    won: bool = False
    created_at: Optional[datetime] = None

@dataclass
class PlaySession:
    """플레이 세션 추적 모델"""
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

@dataclass  
class ClanTeam:
    """클랜 팀 정보"""
    id: Optional[int] = None
    guild_id: str = ""
    clan_name: str = ""
    created_by: str = ""  # 등록한 관리자 ID
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class ClanScrim:
    """클랜전 스크림 세션"""
    id: Optional[int] = None
    guild_id: str = ""
    scrim_uuid: str = ""
    clan_a_name: str = ""
    clan_b_name: str = ""
    voice_channel_a: str = ""
    voice_channel_b: str = ""
    scrim_status: str = "active"  # 'active', 'completed', 'cancelled'
    started_by: str = ""  # 관리자 ID
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    total_matches: int = 0
    clan_a_wins: int = 0
    clan_b_wins: int = 0

@dataclass
class ClanMatch:
    """클랜전 개별 경기"""
    id: Optional[int] = None
    scrim_id: int = 0
    match_uuid: str = ""
    match_number: int = 0  # 1판, 2판, 3판...
    map_name: str = ""
    map_type: Optional[str] = None  # 에스코트, 어솔트, 하이브리드, 컨트롤
    winning_team: str = ""  # 'clan_a' or 'clan_b'
    score_a: Optional[int] = None  # 스코어 (선택사항)
    score_b: Optional[int] = None
    has_position_data: bool = False
    has_composition_data: bool = False
    created_at: Optional[datetime] = None

@dataclass
class ClanParticipant:
    """클랜전 참가자"""
    id: Optional[int] = None
    match_id: int = 0
    user_id: str = ""
    username: str = ""
    clan_name: str = ""
    team_side: str = ""  # 'clan_a' or 'clan_b'
    position: Optional[str] = None  # 탱, 딜, 힐
    position_order: int = 0  # 1-5 (포지션 내 순서)
    won: bool = False
    created_at: Optional[datetime] = None

@dataclass
class ClanComposition:
    """클랜전 팀 조합 (Optional)"""
    id: Optional[int] = None
    match_id: int = 0
    team_side: str = ""  # 'clan_a' or 'clan_b'
    hero_1: Optional[str] = None  # 탱커
    hero_2: Optional[str] = None  # 딜러1
    hero_3: Optional[str] = None  # 딜러2  
    hero_4: Optional[str] = None  # 힐러1
    hero_5: Optional[str] = None  # 힐러2
    composition_type: Optional[str] = None  # 다이브, 벙커, 브롤 등 (나중에 추가)
    created_at: Optional[datetime] = None

@dataclass
class ClanMatchStats:
    """클랜전 통계 (분석용)"""
    clan_name: str
    total_matches: int = 0
    total_wins: int = 0
    total_losses: int = 0
    win_rate: float = 0.0
    favorite_maps: List[str] = None
    recent_form: str = ""  # "W-W-L-W-L" 최근 5경기

@dataclass
class ClanVersusStats:
    """클랜 간 상성 통계"""
    clan_a: str
    clan_b: str
    clan_a_wins: int = 0
    clan_b_wins: int = 0
    total_matches: int = 0
    last_match_date: Optional[datetime] = None
    
@dataclass
class MapStats:
    """맵별 통계"""
    map_name: str
    map_type: str
    total_matches: int = 0
    clan_performance: dict = None

@dataclass
class ServerSettings:
    """서버 설정 데이터 모델"""
    id: Optional[int] = None
    guild_id: str = ""
    newbie_role_id: Optional[str] = None
    member_role_id: Optional[str] = None
    auto_role_change: bool = False
    welcome_channel_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class ServerSettings:
    """서버 설정 데이터 모델"""
    id: Optional[int] = None
    guild_id: str = ""
    
    newbie_role_id: Optional[str] = None     
    member_role_id: Optional[str] = None      
    auto_role_change: bool = False            
    
    new_member_role_id: Optional[str] = None  
    auto_assign_new_member: bool = False      
    
    welcome_channel_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class TeammatePairStats:
    """팀메이트 페어 승률 통계"""
    teammate_id: str
    teammate_name: str
    my_position: str
    teammate_position: str
    total_games: int
    wins: int
    winrate: float
    
    def __post_init__(self):
        """승률 자동 계산"""
        if self.total_games > 0:
            self.winrate = round((self.wins / self.total_games) * 100, 1)
        else:
            self.winrate = 0.0

@dataclass
class BestPairSummary:
    """베스트 페어 요약"""
    tank_pair: Optional[TeammatePairStats] = None
    support_pair: Optional[TeammatePairStats] = None  
    dps_pair: Optional[TeammatePairStats] = None

@dataclass
class TeamWinrateAnalysis:
    """팀 승률 종합 분석 - 동료 승률 시스템"""
    user_id: str
    username: str
    tank_pairs: List[TeammatePairStats]    # 탱커 동료들
    support_pairs: List[TeammatePairStats] # 힐러 동료들
    dps_pairs: List[TeammatePairStats]     # 딜러 동료들
    best_pairs: BestPairSummary
    actual_team_games: int = 0

    def get_total_team_games(self) -> int:
        """실제 팀 경기 이 횟수 (중복 제거)"""
        return self.actual_team_games
    
    def get_overall_team_winrate(self) -> float:
        """전체 팀 승률 (실제 경기 기준)"""
        if self.actual_team_games == 0:
            return 0.0
        
        # 모든 동료들의 승률을 가중평균으로 계산
        all_teammates = self.tank_pairs + self.support_pairs + self.dps_pairs
        if not all_teammates:
            return 0.0
        
        total_weighted_wins = 0
        total_weighted_games = 0
        
        for teammate in all_teammates:
            # 각 동료와의 경기에서 가중치 적용
            total_weighted_wins += teammate.wins
            total_weighted_games += teammate.total_games
        
        if total_weighted_games == 0:
            return 0.0
        
        # 실제 경기 수를 고려한 보정
        # (동료별 경기는 중복 계산되므로 실제 경기 수로 나누어 보정)
        games_per_match = total_weighted_games / self.actual_team_games if self.actual_team_games > 0 else 1
        adjusted_winrate = (total_weighted_wins / total_weighted_games) * 100
        
        return round(adjusted_winrate, 1)

@dataclass
class WordleGame:
    """등록된 띵지워들 게임"""
    id: Optional[int] = None
    guild_id: str = ""
    word: str = ""  # 정답 단어 (5글자)
    hint: Optional[str] = None  # 힌트
    creator_id: str = ""  # 출제자 Discord ID
    creator_username: str = ""
    bet_points: int = 0  # 출제자가 베팅한 포인트
    total_pool: int = 0  # 현재 총 포인트 풀 (출제자 베팅 + 누적 실패분)
    
    # 게임 상태
    is_active: bool = True
    is_completed: bool = False
    winner_id: Optional[str] = None  # 정답자 ID
    winner_username: Optional[str] = None
    
    # 시간 관련
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # 24시간 후 만료
    completed_at: Optional[datetime] = None

@dataclass
class WordleAttempt:
    """띵지워들 도전 기록"""
    id: Optional[int] = None
    game_id: int = 0
    user_id: str = ""  # 도전자 Discord ID
    username: str = ""
    
    # 베팅 관련
    bet_amount: int = 0  # 도전자가 베팅한 포인트
    remaining_points: int = 0  # 남은 포인트 (실패할 때마다 차감)
    points_per_failure: int = 0  # 실패당 차감 포인트 (베팅액의 10%)
    
    # 게임 진행 상황
    attempts_used: int = 0  # 사용한 시도 횟수
    is_completed: bool = False  # 정답 맞춤 또는 포인트 소진으로 완료
    is_winner: bool = False  # 정답을 맞췄는지 여부
    
    # 시간 관련
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

@dataclass
class WordleGuess:
    """띵지워들 추측 기록"""
    id: Optional[int] = None
    attempt_id: int = 0  # WordleAttempt의 ID
    guess_word: str = ""  # 추측한 단어
    result_pattern: str = ""  # 결과 패턴 (예: "12021" - 1:정답, 2:다른위치, 0:없음)
    guess_number: int = 0  # 몇 번째 추측인지 (1, 2, 3...)
    
    created_at: Optional[datetime] = None

@dataclass
class WordleRating:
    """띵지워들 난이도 평가"""
    id: Optional[int] = None
    game_id: int = 0
    user_id: str = ""  # 평가자 Discord ID
    username: str = ""
    rating: str = ""  # "쉬움", "적절함", "어려움"
    
    created_at: Optional[datetime] = None

@dataclass
class WordleUserStats:
    """띵지워들 사용자 통계 (분석용)"""
    user_id: str
    username: str
    
    # 출제 통계
    games_created: int = 0
    games_solved: int = 0  # 출제한 게임 중 정답자가 나온 횟수
    avg_difficulty_rating: float = 0.0  # 평균 난이도 평가
    total_creator_earnings: int = 0  # 출제자로서 번 포인트
    
    # 도전 통계
    games_attempted: int = 0
    games_won: int = 0  # 정답 맞춘 횟수
    avg_attempts_to_solve: float = 0.0  # 평균 시도 횟수
    total_points_won: int = 0  # 도전자로서 번 포인트
    total_points_lost: int = 0  # 도전자로서 잃은 포인트
    
    # 종합 통계
    current_points: int = 0
    win_rate: float = 0.0  # 도전 성공률
    
    last_activity: Optional[datetime] = None

@dataclass
class WordleGameStats:
    """띵지워들 게임별 통계 (분석용)"""
    game_id: int
    word: str
    creator_username: str
    
    # 참여 통계
    total_attempts: int = 0  # 총 도전자 수
    total_guesses: int = 0  # 총 추측 횟수
    avg_attempts_per_challenger: float = 0.0
    
    # 난이도 평가
    easy_votes: int = 0
    appropriate_votes: int = 0
    hard_votes: int = 0
    difficulty_consensus: Optional[str] = None  # 최종 난이도 평가
    
    # 결과
    was_solved: bool = False
    solver_username: Optional[str] = None
    final_pool_amount: int = 0
    
    completed_at: Optional[datetime] = None

@dataclass
class ScrimRecruitment:
    """스크림 모집 데이터 모델"""
    id: Optional[str] = None
    guild_id: str = ""
    title: str = ""
    content: Optional[str] = None
    tier_range: str = ""  # "다이아", "플래티넘~다이아" 등
    opponent_team: Optional[str] = None  # 옵셔널 상대팀 정보
    scrim_date: str = ""  # ISO 형식 datetime
    deadline_date: str = ""  # ISO 형식 datetime
    channel_id: Optional[str] = None  # 공지 채널
    max_participants: int = 5
    status: str = "active"  # 'active', 'closed', 'cancelled'
    created_by: str = ""
    created_at: Optional[datetime] = None

@dataclass
class ScrimParticipant:
    """스크림 참가자 데이터 모델"""
    id: Optional[int] = None
    recruitment_id: str = ""
    user_id: str = ""
    username: str = ""
    status: str = ""  # 'joined', 'declined', 'late_join'
    joined_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class ScrimMatch:
    """스크림 경기 결과 데이터 모델"""
    id: Optional[str] = None
    recruitment_id: str = ""
    match_number: int = 1
    our_team_score: int = 0
    opponent_team_score: int = 0
    winning_team: str = ""  # 'our_team', 'opponent_team'
    map_name: Optional[str] = None
    match_date: Optional[datetime] = None
    created_by: str = ""
    guild_id: str = ""

@dataclass
class ScrimMatchParticipant:
    """스크림 경기 참가자 데이터 모델"""
    id: Optional[int] = None
    match_id: str = ""
    user_id: str = ""
    username: str = ""
    position: str = ""  # '탱커', '딜러', '힐러'
    won: bool = False
    created_at: Optional[datetime] = None