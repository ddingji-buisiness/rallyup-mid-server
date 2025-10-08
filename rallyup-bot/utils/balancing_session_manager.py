import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class BalancingSession:
    """개별 밸런싱 세션 데이터 클래스"""
    
    def __init__(
        self,
        guild_id: str,
        team_a: List[Dict],
        team_b: List[Dict],
        team_a_positions: Dict[str, str],
        team_b_positions: Dict[str, str],
        balancing_mode: str,
        created_by: str
    ):
        self.session_id = str(uuid.uuid4())
        self.guild_id = guild_id
        self.team_a = team_a  # [{'user_id': '...', 'username': '...', 'tier': '...'}, ...]
        self.team_b = team_b
        self.team_a_positions = team_a_positions  # {'user_id': 'position', ...}
        self.team_b_positions = team_b_positions
        self.balancing_mode = balancing_mode  # 'auto' or 'check'
        self.created_by = created_by  # 세션 생성자 user_id
        self.created_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(hours=2)  # 2시간 유효
        self.status = 'ready'  # ready / in_game / completed / expired / cancelled
        self.message_id = None  # 영구 메시지 ID (나중에 설정)
        self.channel_id = None  # 메시지가 전송된 채널 ID
        
    def to_dict(self) -> Dict[str, Any]:
        """세션 데이터를 딕셔너리로 변환"""
        return {
            'session_id': self.session_id,
            'guild_id': self.guild_id,
            'team_a': self.team_a,
            'team_b': self.team_b,
            'team_a_positions': self.team_a_positions,
            'team_b_positions': self.team_b_positions,
            'balancing_mode': self.balancing_mode,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'status': self.status,
            'message_id': self.message_id,
            'channel_id': self.channel_id
        }
    
    def is_expired(self) -> bool:
        """세션이 만료되었는지 확인"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """세션이 유효한지 확인"""
        return not self.is_expired() and self.status in ['ready', 'in_game']
    
    def mark_in_game(self):
        """게임 진행 중 상태로 변경"""
        self.status = 'in_game'
    
    def mark_completed(self):
        """게임 완료 상태로 변경"""
        self.status = 'completed'
    
    def mark_cancelled(self):
        """세션 취소 상태로 변경"""
        self.status = 'cancelled'

    def mark_waiting_rematch(self):
        """재경기 대기 상태로 변경"""
        self.status = 'waiting_rematch'
    
    def get_all_participants(self) -> List[Dict]:
        """현재 세션의 모든 참가자 리스트 반환"""
        return self.team_a + self.team_b
    
    def update_teams(
        self, 
        new_team_a: List[Dict], 
        new_team_b: List[Dict],
        new_team_a_positions: Dict[str, str],
        new_team_b_positions: Dict[str, str]
    ):
        """팀 구성 업데이트 (재밸런싱 시 사용)"""
        self.team_a = new_team_a
        self.team_b = new_team_b
        self.team_a_positions = new_team_a_positions
        self.team_b_positions = new_team_b_positions
        self.status = 'ready'


class BalancingSessionManager:
    """밸런싱 세션 전역 관리자"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.sessions: Dict[str, BalancingSession] = {}  # session_id: BalancingSession
        self.guild_sessions: Dict[str, List[str]] = {}  # guild_id: [session_id, ...]
        self._cleanup_task = None
        self._initialized = True
        logger.info("BalancingSessionManager 초기화 완료")
    
    def create_session(
        self,
        guild_id: str,
        team_a: List[Dict],
        team_b: List[Dict],
        team_a_positions: Dict[str, str],
        team_b_positions: Dict[str, str],
        balancing_mode: str,
        created_by: str
    ) -> BalancingSession:
        """새 세션 생성"""
        session = BalancingSession(
            guild_id=guild_id,
            team_a=team_a,
            team_b=team_b,
            team_a_positions=team_a_positions,
            team_b_positions=team_b_positions,
            balancing_mode=balancing_mode,
            created_by=created_by
        )
        
        # 세션 저장
        self.sessions[session.session_id] = session
        
        # 길드별 세션 목록에 추가
        if guild_id not in self.guild_sessions:
            self.guild_sessions[guild_id] = []
        self.guild_sessions[guild_id].append(session.session_id)
        
        logger.info(f"새 밸런싱 세션 생성: {session.session_id[:8]} (길드: {guild_id})")
        return session
    
    def get_session(self, session_id: str) -> Optional[BalancingSession]:
        """세션 ID로 세션 조회"""
        session = self.sessions.get(session_id)
        
        if session and session.is_expired():
            logger.warning(f"만료된 세션 조회 시도: {session_id[:8]}")
            return None
        
        return session
    
    def get_guild_active_sessions(self, guild_id: str) -> List[BalancingSession]:
        """특정 길드의 활성 세션 목록 조회"""
        if guild_id not in self.guild_sessions:
            return []
        
        active_sessions = []
        for session_id in self.guild_sessions[guild_id]:
            session = self.sessions.get(session_id)
            if session and session.is_valid():
                active_sessions.append(session)
        
        return active_sessions
    
    def update_session_message(self, session_id: str, message_id: str, channel_id: str):
        """세션에 메시지 정보 업데이트"""
        session = self.get_session(session_id)
        if session:
            session.message_id = message_id
            session.channel_id = channel_id
            logger.info(f"세션 메시지 정보 업데이트: {session_id[:8]}")
    
    def mark_session_in_game(self, session_id: str) -> bool:
        """세션을 게임 중 상태로 변경"""
        session = self.get_session(session_id)
        if session:
            session.mark_in_game()
            logger.info(f"세션 상태 변경: {session_id[:8]} -> in_game")
            return True
        return False
    
    def complete_session(self, session_id: str) -> bool:
        """세션 완료 처리"""
        session = self.get_session(session_id)
        if session:
            session.mark_completed()
            logger.info(f"세션 완료: {session_id[:8]}")
            return True
        return False
    
    def cancel_session(self, session_id: str) -> bool:
        """세션 취소"""
        session = self.get_session(session_id)
        if session:
            session.mark_cancelled()
            logger.info(f"세션 취소: {session_id[:8]}")
            return True
        return False
    
    def remove_session(self, session_id: str):
        """세션 삭제"""
        session = self.sessions.get(session_id)
        if session:
            guild_id = session.guild_id
            
            # 길드 세션 목록에서 제거
            if guild_id in self.guild_sessions:
                self.guild_sessions[guild_id].remove(session_id)
                if not self.guild_sessions[guild_id]:
                    del self.guild_sessions[guild_id]
            
            # 세션 삭제
            del self.sessions[session_id]
            logger.info(f"세션 삭제: {session_id[:8]}")
    
    async def cleanup_expired_sessions(self):
        """만료된 세션 정리 (주기적 실행)"""
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session in self.sessions.items():
            if session.is_expired() or session.status in ['completed', 'cancelled']:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.remove_session(session_id)
        
        if expired_sessions:
            logger.info(f"{len(expired_sessions)}개의 만료된 세션 정리 완료")
    
    async def start_cleanup_task(self):
        """자동 정리 태스크 시작"""
        if self._cleanup_task and not self._cleanup_task.done():
            return
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("세션 자동 정리 태스크 시작")
    
    async def _cleanup_loop(self):
        """자동 정리 루프"""
        while True:
            try:
                await asyncio.sleep(600)  # 10분마다 실행
                await self.cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"세션 정리 중 오류: {e}", exc_info=True)
    
    def get_stats(self) -> Dict[str, int]:
        """세션 통계 조회"""
        stats = {
            'total': len(self.sessions),
            'ready': 0,
            'in_game': 0,
            'completed': 0,
            'expired': 0,
            'cancelled': 0
        }
        
        for session in self.sessions.values():
            if session.is_expired():
                stats['expired'] += 1
            else:
                stats[session.status] += 1
        
        return stats

    def mark_waiting_rematch(self, session_id: str) -> bool:
        """세션을 재경기 대기 상태로 변경"""
        session = self.get_session(session_id)
        if session:
            session.mark_waiting_rematch()
            logger.info(f"세션 상태 변경: {session_id[:8]} -> waiting_rematch")
            return True
        return False


session_manager = BalancingSessionManager()