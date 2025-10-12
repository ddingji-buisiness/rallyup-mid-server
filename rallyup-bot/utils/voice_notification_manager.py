"""
음성 레벨 시스템 - 알림 발송 관리
Phase 3: 하이브리드 알림 시스템 + 스마트 업데이트
"""

import discord
import logging
from typing import List, Optional, Dict, Set, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class VoiceNotificationManager:
    """알림 발송 관리 - 하이브리드 시스템"""
    
    # 관계 마일스톤 (시간)
    RELATIONSHIP_MILESTONES = [1, 5, 10, 20, 50, 100, 200, 500]
    SPECIAL_MILESTONES = [50, 100, 200, 500]
    
    # 마일스톤 메시지 템플릿
    MILESTONE_TEMPLATES = {
        1: "🎉 {users}가 처음으로 **1시간**을 함께 플레이했습니다!",
        5: "🔥 {users}가 함께한 시간이 **5시간**을 돌파했습니다!",
        10: "💎 {users}가 **10시간**을 함께 플레이!",
        20: "⭐ {users}가 **20시간** 달성!",
        50: "🏆 {users}가 **50시간** 달성! 진정한 단짝입니다!",
        100: "👑 {users}가 **100시간** 돌파! 전설의 듀오!",
        200: "💫 {users}가 **200시간** 달성! 놀라운 인연입니다!",
        500: "🌟 {users}가 **500시간** 돌파! 영원한 파트너!",
    }
    
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager
        
        # ===== 레벨업 알림용 디바운싱 =====
        self.levelup_debounce = {}  # {(guild_id, user_id, level): timestamp}
        self.debounce_seconds = 60
        
        # ===== 마일스톤 라이브 업데이트 =====
        self.milestone_messages = {}  # {guild_id: message_id}
        self.recent_milestones = {}  # {guild_id: [message_text, ...]}
        self.max_milestone_messages = 10  # 최대 10개 메시지 표시
        self.resend_threshold = 15  # 15개 메시지 이후 재발송
        
        # ===== 중복 방지 (기존 로직) =====
        self.recent_notifications: Dict[Tuple[str, str, str], List[datetime]] = {}
        self.recent_channel_notifications: Dict[Tuple[str, str, int], datetime] = {}
        
        logger.info("✅ VoiceNotificationManager initialized (Hybrid Mode)")

    @staticmethod
    def is_special_milestone(milestone_hours: int) -> bool:
        """특별 마일스톤인지 확인"""
        return milestone_hours in VoiceNotificationManager.SPECIAL_MILESTONES
    
    # ========================================
    # 레벨업 알림 (개별 알림 + 디바운싱)
    # ========================================
    
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
        """레벨업 알림 발송 (기존 방식 + 디바운싱)"""
        try:
            guild_id = str(guild.id)
            user_id = str(member.id)
            
            # ✅ 디바운싱 체크
            debounce_key = (guild_id, user_id, new_level)
            if debounce_key in self.levelup_debounce:
                last_time = self.levelup_debounce[debounce_key]
                elapsed = (datetime.utcnow() - last_time).total_seconds()
                
                if elapsed < self.debounce_seconds:
                    logger.debug(f"⏸️ Levelup debounced: {member.name} Lv{new_level}")
                    return
            
            # 설정 조회
            settings = await self.db.get_voice_level_settings(guild_id)
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
            
            # 특별 레벨 (5의 배수)
            if new_level % 5 == 0 and new_level > 0:
                message += f"\n⏱️ 총 플레이 시간: 약 **{total_play_hours}시간**"
                message += f"\n🤝 함께 플레이한 사람: **{unique_partners}명**"
            
            # 매우 특별한 레벨 (10, 20, 30...)
            if new_level >= 10 and new_level % 10 == 0:
                message += f"\n💎 총 누적 EXP: **{total_exp:,}**"
                
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
            
            # 디바운싱 기록
            self.levelup_debounce[debounce_key] = datetime.utcnow()
            
            logger.info(f"📢 Levelup sent: {member.name} Lv{new_level}")
        
        except Exception as e:
            logger.error(f"Error sending levelup: {e}", exc_info=True)
    
    # ========================================
    # 마일스톤 알림 (기존 방식 + 스마트 업데이트)
    # ========================================
    
    async def add_milestone_event(
        self,
        guild: discord.Guild,
        users: List[discord.Member],
        milestone: int,
        channel_id: str = None
    ):
        """
        마일스톤 이벤트 추가 및 스마트 업데이트
        
        Args:
            guild: 서버
            users: 관련 유저들 (2명 또는 3명 이상)
            milestone: 마일스톤 시간
            channel_id: 음성 채널 ID (중복 방지용)
        """
        try:
            guild_id = str(guild.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            notification_channel_id = settings.get('notification_channel_id')
            if not notification_channel_id:
                return
            
            channel = guild.get_channel(int(notification_channel_id))
            if not channel:
                return
            
            # ✅ 채널 중복 체크 (기존 로직)
            if channel_id and len(users) >= 3:
                if not await self._can_send_channel_notification(guild_id, channel_id, milestone):
                    logger.debug(f"Milestone skipped (cooldown): {milestone}h")
                    return
            
            # ✅ 페어 중복 체크 (기존 로직)
            if len(users) == 2:
                if not await self._can_send_notification(guild_id, str(users[0].id), str(users[1].id)):
                    logger.debug(f"Milestone skipped (pair cooldown): {users[0].name}-{users[1].name}")
                    return
            
            # ✅ 메시지 생성 (기존 템플릿)
            message_text = self._create_milestone_message(users, milestone)
            
            # ✅ 최근 이벤트에 추가
            if guild_id not in self.recent_milestones:
                self.recent_milestones[guild_id] = []
            
            self.recent_milestones[guild_id].append(message_text)
            self.recent_milestones[guild_id] = self.recent_milestones[guild_id][-self.max_milestone_messages:]
            
            # ✅ 스마트 업데이트 (Edit or Resend)
            await self._update_milestone_message(guild, channel)
            
            # ✅ 중복 방지 기록
            if len(users) == 2:
                self._record_notification(guild_id, str(users[0].id), str(users[1].id))
            
            if channel_id and len(users) >= 3:
                self._record_channel_notification(guild_id, channel_id, milestone)
            
            logger.info(f"📊 Milestone added: {len(users)} users, {milestone}h")
        
        except Exception as e:
            logger.error(f"Error adding milestone event: {e}", exc_info=True)
    
    def _create_milestone_message(self, users: List[discord.Member], milestone: int) -> str:
        """마일스톤 메시지 생성 (기존 방식)"""
        # 유저 멘션 생성
        if len(users) == 2:
            user_text = f"{users[0].mention} ↔ {users[1].mention}"
        else:
            user_text = ", ".join([user.mention for user in users])
        
        # 템플릿 가져오기
        template = self.MILESTONE_TEMPLATES.get(
            milestone,
            f"✨ {{users}}가 **{milestone}시간**을 함께 플레이했습니다!"
        )
        
        return template.format(users=user_text)
    
    async def _update_milestone_message(self, guild: discord.Guild, channel: discord.TextChannel):
        """마일스톤 메시지 스마트 업데이트"""
        try:
            guild_id = str(guild.id)
            
            # 이벤트 없으면 스킵
            if guild_id not in self.recent_milestones or not self.recent_milestones[guild_id]:
                return
            
            # ✅ 텍스트 형식으로 메시지 구성
            message_lines = self.recent_milestones[guild_id]
            message_content = "\n".join(message_lines)
            
            # ✅ Edit or Resend 결정
            if guild_id in self.milestone_messages:
                message_id = self.milestone_messages[guild_id]
                
                try:
                    old_message = await channel.fetch_message(message_id)
                    
                    # 마지막 메시지 이후 채팅 개수 체크
                    should_resend = await self._should_resend_message(channel, old_message)
                    
                    if should_resend:
                        # 재발송
                        await old_message.delete()
                        new_message = await channel.send(message_content)
                        self.milestone_messages[guild_id] = new_message.id
                        logger.info(f"🔄 Milestone message resent (채팅 {self.resend_threshold}개 이상)")
                    else:
                        # 조용히 수정
                        await old_message.edit(content=message_content)
                        logger.info(f"✏️ Milestone message edited")
                
                except discord.NotFound:
                    # 메시지 삭제됨 - 새로 발송
                    new_message = await channel.send(message_content)
                    self.milestone_messages[guild_id] = new_message.id
            else:
                # 첫 발송
                new_message = await channel.send(message_content)
                self.milestone_messages[guild_id] = new_message.id
        
        except discord.Forbidden:
            logger.error(f"No permission in {channel.name}")
        except Exception as e:
            logger.error(f"Error updating milestone message: {e}", exc_info=True)
    
    async def _should_resend_message(
        self, 
        channel: discord.TextChannel, 
        old_message: discord.Message
    ) -> bool:
        """재발송 여부 결정 (team_info 로직)"""
        try:
            messages_after = 0
            
            async for message in channel.history(limit=50, after=old_message.created_at):
                if not message.author.bot:
                    messages_after += 1
            
            return messages_after >= self.resend_threshold
        
        except:
            return False
    
    # ========================================
    # 특별 마일스톤 Embed (기존 로직)
    # ========================================
    
    async def send_special_milestone_embed(
        self,
        guild: discord.Guild,
        user1: discord.Member,
        user2: discord.Member,
        milestone: int,
        total_hours: float
    ):
        """특별 마일스톤 Embed 발송 (기존 방식 유지)"""
        try:
            guild_id = str(guild.id)
            
            # 중복 체크
            if not await self._can_send_notification(guild_id, str(user1.id), str(user2.id)):
                logger.debug(f"Special milestone skipped: {user1.name}-{user2.name} {milestone}h")
                return
            
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            channel_id = settings.get('notification_channel_id')
            if not channel_id:
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                return
            
            # 마일스톤별 내용
            if milestone == 50:
                emoji = "🏆"
                title = "진정한 단짝!"
                description = f"{user1.mention}와 {user2.mention}가 **50시간**을 함께 플레이했습니다!"
                color = discord.Color.from_rgb(255, 215, 0)
                status = "진정한 단짝"
            elif milestone == 100:
                emoji = "👑"
                title = "전설의 듀오!"
                description = f"{user1.mention}와 {user2.mention}가 **100시간**을 돌파했습니다!"
                color = discord.Color.from_rgb(147, 51, 234)
                status = "전설의 듀오"
            elif milestone == 200:
                emoji = "💫"
                title = "놀라운 인연!"
                description = f"{user1.mention}와 {user2.mention}가 **200시간**을 달성했습니다!"
                color = discord.Color.from_rgb(59, 130, 246)
                status = "놀라운 인연"
            elif milestone >= 500:
                emoji = "🌟"
                title = "영원한 파트너!"
                description = f"{user1.mention}와 {user2.mention}가 **{milestone}시간**을 돌파했습니다!"
                color = discord.Color.from_rgb(236, 72, 153)
                status = "영원한 파트너"
            else:
                emoji = "✨"
                title = "특별한 순간!"
                description = f"{user1.mention}와 {user2.mention}가 **{milestone}시간**을 함께 플레이했습니다!"
                color = discord.Color.gold()
                status = "특별한 관계"
            
            # Embed 생성
            embed = discord.Embed(
                title=f"{emoji} {title}",
                description=description,
                color=color
            )
            
            embed.add_field(
                name="⏱️ 함께한 시간",
                value=f"**{int(total_hours)}시간 {int((total_hours % 1) * 60)}분**",
                inline=True
            )
            
            embed.add_field(
                name="🎯 관계 등급",
                value=f"**{status}**",
                inline=True
            )
            
            # 발송
            await channel.send(embed=embed)
            
            # 중복 방지 기록
            self._record_notification(guild_id, str(user1.id), str(user2.id))
            
            logger.info(f"📢 Special milestone embed sent: {user1.name}-{user2.name} {milestone}h")
        
        except Exception as e:
            logger.error(f"Error sending special milestone embed: {e}", exc_info=True)
    
    # ========================================
    # 중복 방지 (기존 로직)
    # ========================================
    
    async def _can_send_notification(
        self,
        guild_id: str,
        user1_id: str,
        user2_id: str,
        max_per_day: int = 3
    ) -> bool:
        """페어별 중복 체크"""
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        key = (guild_id, user1_id, user2_id)
        now = datetime.utcnow()
        
        if key not in self.recent_notifications:
            return True
        
        cutoff = now - timedelta(hours=24)
        recent = [ts for ts in self.recent_notifications[key] if ts > cutoff]
        
        if recent:
            self.recent_notifications[key] = recent
        else:
            del self.recent_notifications[key]
            return True
        
        return len(recent) < max_per_day
    
    def _record_notification(self, guild_id: str, user1_id: str, user2_id: str):
        """알림 발송 기록"""
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        key = (guild_id, user1_id, user2_id)
        now = datetime.utcnow()
        
        if key not in self.recent_notifications:
            self.recent_notifications[key] = []
        
        self.recent_notifications[key].append(now)
    
    async def _can_send_channel_notification(
        self,
        guild_id: str,
        channel_id: str,
        milestone: int,
        cooldown_minutes: int = 5
    ) -> bool:
        """채널별 중복 체크"""
        key = (guild_id, channel_id, milestone)
        now = datetime.utcnow()
        
        if key in self.recent_channel_notifications:
            last_time = self.recent_channel_notifications[key]
            elapsed = (now - last_time).total_seconds() / 60.0
            
            if elapsed < cooldown_minutes:
                return False
        
        return True
    
    def _record_channel_notification(self, guild_id: str, channel_id: str, milestone: int):
        """채널 알림 기록"""
        key = (guild_id, channel_id, milestone)
        self.recent_channel_notifications[key] = datetime.utcnow()
    
    def cleanup_old_notifications(self):
        """오래된 기록 정리"""
        try:
            now = datetime.utcnow()
            cutoff_24h = now - timedelta(hours=24)
            cutoff_1h = now - timedelta(hours=1)
            cutoff_debounce = now - timedelta(seconds=self.debounce_seconds * 2)
            
            # 페어별 알림
            keys_to_delete = []
            for key, timestamps in self.recent_notifications.items():
                recent = [ts for ts in timestamps if ts > cutoff_24h]
                if recent:
                    self.recent_notifications[key] = recent
                else:
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.recent_notifications[key]
            
            # 채널별 알림
            channel_keys_to_delete = []
            for key, timestamp in self.recent_channel_notifications.items():
                if timestamp <= cutoff_1h:
                    channel_keys_to_delete.append(key)
            
            for key in channel_keys_to_delete:
                del self.recent_channel_notifications[key]
            
            # 레벨업 디바운싱
            debounce_keys_to_delete = []
            for key, timestamp in self.levelup_debounce.items():
                if timestamp < cutoff_debounce:
                    debounce_keys_to_delete.append(key)
            
            for key in debounce_keys_to_delete:
                del self.levelup_debounce[key]
            
            if keys_to_delete or channel_keys_to_delete or debounce_keys_to_delete:
                logger.debug(f"🧹 Cleaned up notifications")
        
        except Exception as e:
            logger.error(f"Error cleaning up: {e}", exc_info=True)