import discord
import logging
from typing import List, Optional, Dict, Set, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VoiceNotificationManager:
    """알림 발송 관리"""
    
    # 관계 마일스톤 (시간)
    RELATIONSHIP_MILESTONES = [1, 5, 10, 20, 50, 100, 200, 500]
    
    # 알림 템플릿
    MILESTONE_TEMPLATES = {
        1: "🎉 {user1}와 {user2}가 처음으로 **1시간**을 함께 플레이했습니다!",
        5: "🔥 {user1}와 {user2}가 함께한 시간이 **5시간**을 돌파했습니다!",
        10: "💎 {user1}와 {user2}가 **10시간**을 함께 플레이!",
        20: "⭐ {user1}와 {user2}가 **20시간** 달성!",
        50: "🏆 {user1}와 {user2}가 **50시간** 달성! 진정한 단짝입니다!",
        100: "👑 {user1}와 {user2}가 **100시간** 돌파! 전설의 듀오!",
        200: "💫 {user1}와 {user2}가 **200시간** 달성! 놀라운 인연입니다!",
        500: "🌟 {user1}와 {user2}가 **500시간** 돌파! 영원한 파트너!",
    }
    
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager
        
        # 스팸 방지: {(guild_id, user1_id, user2_id): [timestamp1, timestamp2, ...]}
        self.recent_notifications: Dict[Tuple[str, str, str], List[datetime]] = {}
        
        logger.info("✅ VoiceNotificationManager initialized")
    
    async def send_relationship_milestone(
        self,
        guild: discord.Guild,
        user1: discord.Member,
        user2: discord.Member,
        milestone_hours: int,
        exp_gained: int = 0
    ):
        """
        관계 마일스톤 알림 발송
        
        Args:
            guild: 서버
            user1: 유저1
            user2: 유저2
            milestone_hours: 마일스톤 시간
            exp_gained: 획득한 exp (선택)
        """
        try:
            # 설정 조회
            settings = await self.db.get_voice_level_settings(str(guild.id))
            if not settings['enabled']:
                return
            
            channel_id = settings.get('notification_channel_id')
            if not channel_id:
                logger.debug(f"No notification channel set for guild {guild.id}")
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                logger.warning(f"Notification channel {channel_id} not found in guild {guild.id}")
                return
            
            # 스팸 방지 체크
            if not await self._can_send_notification(str(guild.id), str(user1.id), str(user2.id)):
                logger.debug(f"Notification rate limit for {user1.id}-{user2.id}")
                return
            
            # 메시지 생성
            template = self.MILESTONE_TEMPLATES.get(
                milestone_hours,
                f"✨ {{user1}}와 {{user2}}가 **{milestone_hours}시간**을 함께 플레이했습니다!"
            )
            
            message = template.format(
                user1=user1.mention,
                user2=user2.mention
            )
            
            # EXP 정보 추가 (선택)
            if exp_gained > 0:
                message += f"\n+{exp_gained} exp 획득"
            
            # 발송
            await channel.send(message)
            
            # 스팸 방지 기록
            self._record_notification(str(guild.id), str(user1.id), str(user2.id))
            
            logger.info(f"📢 Milestone notification sent: {user1.name}-{user2.name} ({milestone_hours}h)")
        
        except discord.Forbidden:
            logger.error(f"No permission to send message in channel {channel_id}")
        except Exception as e:
            logger.error(f"Error sending milestone notification: {e}", exc_info=True)
    
    async def send_group_milestone(
        self,
        guild: discord.Guild,
        members: List[discord.Member],
        milestone_hours: int
    ):
        """
        그룹 마일스톤 알림 (3명 이상)
        
        Args:
            guild: 서버
            members: 멤버 리스트
            milestone_hours: 마일스톤 시간
        """
        try:
            # 설정 조회
            settings = await self.db.get_voice_level_settings(str(guild.id))
            if not settings['enabled']:
                return
            
            channel_id = settings.get('notification_channel_id')
            if not channel_id:
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return
            
            # 멤버 멘션 리스트 생성
            mentions = ", ".join([member.mention for member in members])
            
            # 메시지 생성
            if milestone_hours == 1:
                message = f"🎊 {mentions}가 처음으로 **1시간**을 함께 플레이했습니다!"
            elif milestone_hours == 5:
                message = f"🔥 {mentions}가 함께한 시간이 **5시간**을 돌파했습니다!"
            elif milestone_hours == 10:
                message = f"💎 {mentions}가 **10시간**을 함께 플레이!"
            else:
                message = f"✨ {mentions}가 **{milestone_hours}시간**을 함께 플레이했습니다!"
            
            # 발송
            await channel.send(message)
            
            logger.info(f"📢 Group milestone notification sent: {len(members)} members ({milestone_hours}h)")
        
        except discord.Forbidden:
            logger.error(f"No permission to send message in channel {channel_id}")
        except Exception as e:
            logger.error(f"Error sending group milestone notification: {e}", exc_info=True)
    
    async def send_levelup_notification(
        self,
        guild: discord.Guild,
        member: discord.Member,
        old_level: int,
        new_level: int,
        total_exp: int,
        total_play_hours: int,
        unique_partners: int
    ):
        """
        레벨업 알림 발송
        
        Args:
            guild: 서버
            member: 멤버
            old_level: 이전 레벨
            new_level: 새 레벨
            total_exp: 총 누적 exp
            total_play_hours: 총 플레이 시간 (시간)
            unique_partners: 고유 파트너 수
        """
        try:
            # 설정 조회
            settings = await self.db.get_voice_level_settings(str(guild.id))
            if not settings['enabled']:
                return
            
            channel_id = settings.get('notification_channel_id')
            if not channel_id:
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return
            
            # 기본 메시지
            message = f"⭐ {member.mention}님이 **Level {new_level}**에 도달했습니다!"
            
            # 특별 레벨 (5의 배수)에는 추가 정보
            if new_level % 5 == 0 and new_level > 0:
                message += f"\n⏱️ 총 플레이 시간: 약 **{total_play_hours}시간**"
                message += f"\n🤝 함께 플레이한 사람: **{unique_partners}명**"
            
            # 매우 특별한 레벨 (10, 20, 30...)
            if new_level >= 10 and new_level % 10 == 0:
                message += f"\n💎 총 누적 EXP: **{total_exp:,}**"
                
                # 축하 이모지 추가
                if new_level == 10:
                    message += "\n🎉 드디어 10레벨! 헌신적인 멤버입니다!"
                elif new_level == 20:
                    message += "\n👑 20레벨 달성! 클랜의 기둥입니다!"
                elif new_level == 30:
                    message += "\n🌟 30레벨! 레전드 플레이어입니다!"
                elif new_level >= 50:
                    message += "\n⚡ 신화적인 업적입니다!"
            
            # 발송
            await channel.send(message)
            
            logger.info(f"📢 Levelup notification sent: {member.name} (Lv {old_level} → {new_level})")
        
        except discord.Forbidden:
            logger.error(f"No permission to send message in channel {channel_id}")
        except Exception as e:
            logger.error(f"Error sending levelup notification: {e}", exc_info=True)
    
    async def check_and_send_milestone_notifications(
        self,
        guild: discord.Guild,
        user_id: str,
        partner_id: str,
        old_hours: float,
        new_hours: float,
        exp_gained: int = 0
    ):
        """
        마일스톤 체크 및 알림 발송
        
        Args:
            guild: 서버
            user_id: 유저 ID
            partner_id: 파트너 ID
            old_hours: 이전 누적 시간 (시간)
            new_hours: 현재 누적 시간 (시간)
            exp_gained: 획득한 exp
        """
        try:
            # 새로 달성한 마일스톤 찾기
            achieved_milestones = []
            
            for milestone in self.RELATIONSHIP_MILESTONES:
                if old_hours < milestone <= new_hours:
                    achieved_milestones.append(milestone)
            
            if not achieved_milestones:
                return
            
            # 멤버 조회
            user = guild.get_member(int(user_id))
            partner = guild.get_member(int(partner_id))
            
            if not user or not partner:
                logger.warning(f"Member not found: {user_id} or {partner_id}")
                return
            
            # 각 마일스톤에 대해 알림 발송
            for milestone in achieved_milestones:
                await self.send_relationship_milestone(
                    guild, user, partner, milestone, exp_gained
                )
        
        except Exception as e:
            logger.error(f"Error checking milestones: {e}", exc_info=True)
    
    async def _can_send_notification(
        self,
        guild_id: str,
        user1_id: str,
        user2_id: str,
        max_per_day: int = 3
    ) -> bool:
        """
        스팸 방지: 같은 페어에 대해 하루 최대 알림 수 체크
        
        Args:
            guild_id: 서버 ID
            user1_id: 유저1 ID
            user2_id: 유저2 ID
            max_per_day: 하루 최대 알림 수
            
        Returns:
            알림 발송 가능 여부
        """
        # user1_id가 항상 작도록 정렬
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        key = (guild_id, user1_id, user2_id)
        now = datetime.utcnow()
        
        # 기존 알림 기록 조회
        if key not in self.recent_notifications:
            return True
        
        # 24시간 이내의 알림만 필터링
        cutoff = now - timedelta(hours=24)
        recent = [ts for ts in self.recent_notifications[key] if ts > cutoff]
        
        # 오래된 기록 정리
        if recent:
            self.recent_notifications[key] = recent
        else:
            del self.recent_notifications[key]
            return True
        
        # 최대 개수 체크
        return len(recent) < max_per_day
    
    def _record_notification(self, guild_id: str, user1_id: str, user2_id: str):
        """알림 발송 기록"""
        # user1_id가 항상 작도록 정렬
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        key = (guild_id, user1_id, user2_id)
        now = datetime.utcnow()
        
        if key not in self.recent_notifications:
            self.recent_notifications[key] = []
        
        self.recent_notifications[key].append(now)
    
    def cleanup_old_notifications(self):
        """오래된 알림 기록 정리 (메모리 관리)"""
        try:
            now = datetime.utcnow()
            cutoff = now - timedelta(hours=24)
            
            keys_to_delete = []
            
            for key, timestamps in self.recent_notifications.items():
                # 24시간 이내의 알림만 필터링
                recent = [ts for ts in timestamps if ts > cutoff]
                
                if recent:
                    self.recent_notifications[key] = recent
                else:
                    keys_to_delete.append(key)
            
            # 빈 키 삭제
            for key in keys_to_delete:
                del self.recent_notifications[key]
            
            if keys_to_delete:
                logger.debug(f"Cleaned up {len(keys_to_delete)} old notification records")
        
        except Exception as e:
            logger.error(f"Error cleaning up notifications: {e}", exc_info=True)