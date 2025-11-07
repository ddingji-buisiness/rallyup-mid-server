"""
음성 채널 세션 추적 및 팀 점수 자동 지급 시스템

기능:
- 실시간 음성 채널 입장/퇴장 추적
- 같은 팀원이 2명 이상 모이면 세션 시작
- 2~4명: 1시간당 1점 (최대 10점)
- 5명+: 1시간 유지 시 즉시 10점
- 일일 최대 10점 제한 (오전 9시 기준)
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
import discord

logger = logging.getLogger(__name__)


@dataclass
class VoiceSession:
    """음성 채널 세션 정보"""
    channel_id: str
    team_id: str
    team_name: str
    guild_id: str
    members: Set[str] = field(default_factory=set)  # user_ids
    start_time: datetime = field(default_factory=datetime.now)
    member_count: int = 0
    is_bonus_mode: bool = False  # 5명 이상 여부
    bonus_start_time: Optional[datetime] = None
    last_check_time: Optional[datetime] = None
    hours_awarded: int = 0
    
    def __post_init__(self):
        self.member_count = len(self.members)
        if self.last_check_time is None:
            self.last_check_time = self.start_time
    
    def update_members(self, members: Set[str]):
        """멤버 업데이트 및 보너스 모드 체크"""
        old_count = self.member_count
        self.members = members
        self.member_count = len(members)
        
        # 5명 이상 → 보너스 모드 진입
        if self.member_count >= 5 and not self.is_bonus_mode:
            self.is_bonus_mode = True
            self.bonus_start_time = datetime.now()
            logger.info(f"🎉 팀 '{self.team_name}' 보너스 모드 진입! ({self.member_count}명)")
        
        # 5명 미만으로 떨어짐 → 보너스 모드 해제
        elif self.member_count < 5 and self.is_bonus_mode:
            self.is_bonus_mode = False
            self.bonus_start_time = None
            logger.info(f"⚠️ 팀 '{self.team_name}' 보너스 모드 해제 ({self.member_count}명)")
    
    def get_elapsed_time(self) -> timedelta:
        """세션 시작 후 경과 시간"""
        return datetime.now() - self.start_time
    
    def get_bonus_elapsed_time(self) -> Optional[timedelta]:
        """보너스 모드 진입 후 경과 시간"""
        if self.bonus_start_time:
            return datetime.now() - self.bonus_start_time
        return None


class VoiceSessionTracker:
    """음성 채널 세션 추적 및 점수 지급 관리"""
    
    TEST_MODE = True
    
    # 점수 관련 상수
    POINTS_PER_HOUR = 1  # 일반 모드 시간당 점수
    BONUS_POINTS = 10  # 5명+ 1시간 유지 시 점수
    MAX_DAILY_POINTS = 10  # 팀당 일일 최대 점수
    BONUS_MEMBER_THRESHOLD = 5  # 보너스 모드 진입 인원
    
    if TEST_MODE:
        HOUR_IN_SECONDS = 60  # 테스트: 1분
        CHECK_INTERVAL = 10  # 테스트: 10초마다 체크
        logger.warning("⚠️ 테스트 모드 활성화! 1시간 = 1분으로 설정됨")
    else:
        HOUR_IN_SECONDS = 3600  # 실제: 1시간
        CHECK_INTERVAL = 60  # 실제: 1분마다 체크

    DAILY_RESET_HOUR = 9  # 오전 9시 기준
    
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager
        
        # 실시간 세션 추적
        # {team_id: {channel_id: VoiceSession}}
        self.active_sessions: Dict[str, Dict[str, VoiceSession]] = {}
        
        # Background task
        self.check_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        logger.info("✅ VoiceSessionTracker 초기화 완료")
    
    async def start(self):
        """Background task 시작"""
        if not self.is_running:
            self.is_running = True
            self.check_task = asyncio.create_task(self._session_check_loop())
            logger.info("🚀 음성 세션 체크 루프 시작")
    
    async def stop(self):
        """Background task 종료"""
        self.is_running = False
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 음성 세션 체크 루프 종료")
    
    def _get_today_date_string(self) -> str:
        """오늘 날짜 문자열 (오전 9시 기준)"""
        now = datetime.now()
        if now.hour < self.DAILY_RESET_HOUR:
            # 오전 9시 이전이면 전날로 계산
            today = now - timedelta(days=1)
        else:
            today = now
        return today.strftime('%Y-%m-%d')
    
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """
        음성 채널 상태 변화 이벤트 처리
        
        Args:
            member: 상태가 변경된 멤버
            before: 변경 전 음성 상태
            after: 변경 후 음성 상태
        """
        # 봇은 무시
        if member.bot:
            return
        
        guild_id = str(member.guild.id)
        user_id = str(member.id)

        logger.info(f"🎤 음성 상태 변경: {member.name} (ID: {user_id})")
        logger.info(f"   Before: {before.channel.name if before.channel else 'None'}")
        logger.info(f"   After: {after.channel.name if after.channel else 'None'}")
        
        # 유저가 속한 팀 조회
        team_info = await self.db.get_user_event_team(guild_id, user_id)
        if not team_info:
            logger.info(f"   ❌ {member.name}은(는) 이벤트 팀에 속하지 않음")
            return  # 이벤트 팀에 속하지 않음
        
        team_id = team_info['team_id']
        team_name = team_info['team_name']
        logger.info(f"   ✅ 팀 확인: {team_name} (ID: {team_id})")
        
        # 채널 입장/퇴장 처리
        if before.channel != after.channel:
            # 퇴장 처리
            if before.channel:
                logger.info(f"   📤 {before.channel.name} 채널 퇴장 처리")
                await self._handle_member_leave(
                    guild_id, team_id, team_name, 
                    str(before.channel.id), before.channel
                )
            
            # 입장 처리
            if after.channel:
                logger.info(f"   📥 {after.channel.name} 채널 입장 처리")
                await self._handle_member_join(
                    guild_id, team_id, team_name,
                    str(after.channel.id), after.channel
                )
    
    async def _handle_member_join(
        self,
        guild_id: str,
        team_id: str,
        team_name: str,
        channel_id: str,
        channel: discord.VoiceChannel
    ):
        """멤버가 음성 채널에 입장했을 때 처리"""
        # 해당 채널에 있는 같은 팀원 수집
        team_members_in_channel = await self._get_team_members_in_channel(
            guild_id, team_id, channel
        )
        
        # 2명 이상이면 세션 생성/업데이트
        if len(team_members_in_channel) >= 2:
            await self._update_or_create_session(
                guild_id, team_id, team_name, channel_id, team_members_in_channel
            )
    
    async def _handle_member_leave(
        self,
        guild_id: str,
        team_id: str,
        team_name: str,
        channel_id: str,
        channel: discord.VoiceChannel
    ):
        """멤버가 음성 채널에서 퇴장했을 때 처리"""
        # 해당 채널에 남은 같은 팀원 수집
        team_members_in_channel = await self._get_team_members_in_channel(
            guild_id, team_id, channel
        )
        
        # 2명 미만이면 세션 종료
        if len(team_members_in_channel) < 2:
            await self._end_session(team_id, channel_id)
        else:
            # 2명 이상 남아있으면 세션 업데이트
            await self._update_or_create_session(
                guild_id, team_id, team_name, channel_id, team_members_in_channel
            )
    
    async def _get_team_members_in_channel(
        self,
        guild_id: str,
        team_id: str,
        channel: discord.VoiceChannel
    ) -> Set[str]:
        """특정 채널에 있는 팀원들의 user_id 세트 반환"""
        team_member_ids = await self.db.get_event_team_member_ids(team_id)
        
        members_in_channel = set()
        for member in channel.members:
            if not member.bot and str(member.id) in team_member_ids:
                members_in_channel.add(str(member.id))
        
        return members_in_channel
    
    async def _update_or_create_session(
        self,
        guild_id: str,
        team_id: str,
        team_name: str,
        channel_id: str,
        members: Set[str]
    ):
        """세션 생성 또는 업데이트"""
        # 팀의 active_sessions 초기화
        if team_id not in self.active_sessions:
            self.active_sessions[team_id] = {}
        
        # 옵션 1 구현: 가장 많은 인원이 있는 채널만 추적
        # 다른 채널에 세션이 있으면 비교
        max_channel_id = channel_id
        max_member_count = len(members)
        
        for existing_channel_id, session in self.active_sessions[team_id].items():
            if session.member_count > max_member_count:
                max_channel_id = existing_channel_id
                max_member_count = session.member_count
        
        # 현재 채널이 최대가 아니면 무시
        if channel_id != max_channel_id:
            logger.info(
                f"📊 팀 '{team_name}': 채널 {channel_id}({len(members)}명)보다 "
                f"채널 {max_channel_id}({max_member_count}명)에 더 많은 인원"
            )
            return
        
        # 기존 세션 제거 (다른 채널)
        channels_to_remove = [
            cid for cid in self.active_sessions[team_id].keys()
            if cid != channel_id
        ]
        for cid in channels_to_remove:
            logger.info(f"🔄 팀 '{team_name}': 채널 {cid} 세션 종료 (최대 인원 채널로 이동)")
            del self.active_sessions[team_id][cid]
        
        # 세션 업데이트 또는 생성
        if channel_id in self.active_sessions[team_id]:
            # 기존 세션 업데이트
            session = self.active_sessions[team_id][channel_id]
            session.update_members(members)
            logger.info(
                f"🔄 세션 업데이트: 팀 '{team_name}', 채널 {channel_id}, "
                f"{session.member_count}명, 보너스: {session.is_bonus_mode}"
            )
        else:
            # 새 세션 생성
            session = VoiceSession(
                channel_id=channel_id,
                team_id=team_id,
                team_name=team_name,
                guild_id=guild_id,
                members=members
            )
            self.active_sessions[team_id][channel_id] = session
            logger.info(
                f"✨ 새 세션 생성: 팀 '{team_name}', 채널 {channel_id}, "
                f"{session.member_count}명"
            )
    
    async def _end_session(self, team_id: str, channel_id: str):
        """세션 종료"""
        if team_id in self.active_sessions:
            if channel_id in self.active_sessions[team_id]:
                session = self.active_sessions[team_id][channel_id]
                logger.info(
                    f"🛑 세션 종료: 팀 '{session.team_name}', 채널 {channel_id}, "
                    f"경과시간: {session.get_elapsed_time()}"
                )
                del self.active_sessions[team_id][channel_id]
            
            # 팀의 모든 세션이 종료되면 팀 항목 삭제
            if not self.active_sessions[team_id]:
                del self.active_sessions[team_id]
    
    async def _session_check_loop(self):
        """1분마다 모든 활성 세션 체크 및 점수 지급"""
        logger.info("⏰ 세션 체크 루프 시작")
        
        while self.is_running:
            try:
                await asyncio.sleep(self.CHECK_INTERVAL)
                
                if not self.active_sessions:
                    continue
                
                logger.debug(f"🔍 세션 체크 중... (활성 팀: {len(self.active_sessions)}개)")
                
                # 모든 활성 세션 체크
                for team_id, channels in list(self.active_sessions.items()):
                    for channel_id, session in list(channels.items()):
                        await self._check_and_award_points(session)
                
            except asyncio.CancelledError:
                logger.info("⏰ 세션 체크 루프 취소됨")
                break
            except Exception as e:
                logger.error(f"❌ 세션 체크 중 오류: {e}", exc_info=True)
    
    async def _check_and_award_points(self, session: VoiceSession):
        """세션 점수 지급 체크"""
        now = datetime.now()
        today_date = self._get_today_date_string()

        logger.info(f"⏰ 점수 체크: 팀 '{session.team_name}', 멤버 {session.member_count}명")

        # 오늘 팀이 받은 점수 조회
        current_score = await self.db.get_voice_team_daily_score(
            session.team_id, today_date
        )
        logger.info(f"   현재 점수: {current_score}/{self.MAX_DAILY_POINTS}")

        # 이미 최대 점수 도달
        if current_score >= self.MAX_DAILY_POINTS:
            logger.debug(f"⏭️ 팀 '{session.team_name}' 일일 최대 점수 도달 ({current_score}점)")
            return
        
        # 보너스 모드 체크
        if session.is_bonus_mode:
            bonus_elapsed = session.get_bonus_elapsed_time()
            logger.info(f"   🎉 보너스 모드! 경과: {bonus_elapsed.total_seconds():.0f}초/{self.HOUR_IN_SECONDS}초")

            if bonus_elapsed and bonus_elapsed.total_seconds() >= self.HOUR_IN_SECONDS:
                # 5명+ 1시간 유지 → 즉시 10점 (또는 남은 점수)
                points_to_award = min(
                    self.BONUS_POINTS,
                    self.MAX_DAILY_POINTS - current_score
                )
                logger.info(f"   💰 보너스 점수 지급 시도: {points_to_award}점")

                if points_to_award > 0:
                    success = await self._award_points(
                        session, 
                        points_to_award, 
                        is_bonus=True,
                        hours_completed=1
                    )
                    
                    if success:
                        logger.info(
                            f"🎉 보너스 점수 지급 성공! 팀 '{session.team_name}': "
                            f"+{points_to_award}점"
                        )
                        await self._end_session(session.team_id, session.channel_id)
                    else:
                        logger.error(f"❌ 보너스 점수 지급 실패!")
        
        # 일반 모드 (2~4명): 1시간마다 1점
        else:
            elapsed = session.get_elapsed_time()
            hours_passed = int(elapsed.total_seconds() // self.HOUR_IN_SECONDS)
            
            # 마지막 체크 이후 1시간이 지났는지
            last_check_elapsed = now - session.last_check_time

            logger.info(f"   📊 일반 모드: 총 경과 {elapsed.total_seconds():.0f}초, "
                   f"마지막 체크 후 {last_check_elapsed.total_seconds():.0f}초")
            
            if last_check_elapsed.total_seconds() >= self.HOUR_IN_SECONDS:
                # 지급 가능한 점수 계산
                points_to_award = min(
                    self.POINTS_PER_HOUR,
                    self.MAX_DAILY_POINTS - current_score
                )
                logger.info(f"   💰 일반 점수 지급 시도: {points_to_award}점")
                
                if points_to_award > 0:
                    session.hours_awarded += 1

                    success = await self._award_points(
                        session, 
                        points_to_award, 
                        is_bonus=False,
                        hours_completed=session.hours_awarded
                    )
                    
                    if success:
                        session.last_check_time = now
                        logger.info(
                            f"✅ 일반 점수 지급 성공! 팀 '{session.team_name}': "
                            f"+{points_to_award}점"
                        )
                    else:
                        session.hours_awarded -= 1
                        logger.error(f"❌ 일반 점수 지급 실패!")
    
    async def _award_points(
        self,
        session: VoiceSession,
        points: int,
        is_bonus: bool,
        hours_completed: int
    ) -> bool:
        """점수 지급 및 DB 저장"""
        try:
            today_date = self._get_today_date_string()
            
            # DB에 점수 저장
            success = await self.db.add_voice_team_score(
                team_id=session.team_id,
                date=today_date,
                points=points,
                session_data={
                    'channel_id': session.channel_id,
                    'member_count': session.member_count,
                    'is_bonus': is_bonus,
                    'hours_completed': hours_completed,
                    'start_time': session.start_time.isoformat(),
                    'awarded_at': datetime.now().isoformat()
                }
            )

            if success:
                # 공지 채널에 메시지 발송
                await self._send_voice_activity_announcement(
                    session=session,
                    points=points,
                    is_bonus=is_bonus,
                    hours_completed=hours_completed
                )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 점수 지급 실패: {e}", exc_info=True)
            return False
    
    async def get_today_score(self, team_id: str) -> int:
        """팀의 오늘 점수 조회 (일일 퀘스트 연동용)"""
        today_date = self._get_today_date_string()
        return await self.db.get_voice_team_daily_score(team_id, today_date)
    
    def get_active_sessions_info(self) -> List[Dict]:
        """현재 활성 세션 정보 조회 (디버깅/관리용)"""
        info = []
        for team_id, channels in self.active_sessions.items():
            for channel_id, session in channels.items():
                info.append({
                    'team_id': team_id,
                    'team_name': session.team_name,
                    'channel_id': channel_id,
                    'member_count': session.member_count,
                    'is_bonus_mode': session.is_bonus_mode,
                    'elapsed_seconds': session.get_elapsed_time().total_seconds(),
                    'bonus_elapsed_seconds': (
                        session.get_bonus_elapsed_time().total_seconds()
                        if session.get_bonus_elapsed_time() else None
                    )
                })
        return info
    
    async def _send_voice_activity_announcement(
        self,
        session: VoiceSession,
        points: int,
        is_bonus: bool,
        hours_completed: int
    ):
        """음성 활동 점수 획득 공지 메시지 발송"""
        try:
            logger.info(f"📢 공지 발송 시도: {session.team_name} +{points}점")

            # 공지 채널 ID 조회
            channel_id = await self.db.get_event_announcement_channel(session.guild_id)
            if not channel_id:
                return  # 공지 채널 미설정
            
            logger.info(f"   공지 채널 ID: {channel_id}")
            
            # 채널 가져오기
            guild = self.bot.get_guild(int(session.guild_id))
            if not guild:
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return
            
            # 메시지 생성
            if is_bonus:
                activity_type = "🎉 **5명 이상 1시간 함께 플레이**"
                emoji = "🎊"
            else:
                activity_type = f"🎤 **{session.member_count}명이 {hours_completed}시간 함께 플레이**"
                emoji = "✨"
            
            # 오늘 총 점수 조회
            today_score = await self.db.get_voice_team_daily_score(
                session.team_id, 
                self._get_today_date_string()
            )
            
            message = (
                f"{emoji} **{session.team_name}** 팀 "
                f"{activity_type} 미션을 완료했습니다! "
                f"**(+{points}점)**"
            )
            
            if today_score >= self.MAX_DAILY_POINTS:
                message += f"\n🏆 **오늘 음성 활동 최대 점수 달성!** (일일 {self.MAX_DAILY_POINTS}점)"
            else:
                remaining = self.MAX_DAILY_POINTS - today_score
                message += f"\n💡 오늘 남은 음성 활동 점수: **{remaining}점**"
            
            # 메시지 발송
            await channel.send(message)
            logger.info(f"📢 음성 활동 공지 발송: {session.team_name} +{points}점 ({hours_completed}시간째)")
            
        except Exception as e:
            logger.error(f"❌ 음성 활동 공지 발송 실패: {e}", exc_info=True)