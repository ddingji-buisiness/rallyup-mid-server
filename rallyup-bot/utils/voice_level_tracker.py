import discord
from discord.ext import tasks
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple
import asyncio
from utils.voice_exp_calculator import VoiceExpCalculator
from utils.voice_notification_manager import VoiceNotificationManager

logger = logging.getLogger(__name__)


class VoiceLevelTracker:
    """음성 채널 활동 추적 및 관계 시간 누적"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.exp_calculator = VoiceExpCalculator(self.db)
        self.active_sessions: Dict[Tuple[str, str], str] = {}
        self.notification_manager = VoiceNotificationManager(bot, self.db)
        self.relationship_update_task.start()
        logger.info("✅ VoiceLevelTracker initialized")
    
    async def handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """음성 채널 입장 처리"""
        try:
            # 봇 제외
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            channel_id = str(channel.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            # 음소거 상태 확인
            is_muted = member.voice.self_mute if member.voice else False
            
            # 세션 생성
            session_uuid = await self.db.create_voice_session(
                guild_id, user_id, channel_id, is_muted
            )
            
            # 메모리 캐시 업데이트
            self.active_sessions[(guild_id, user_id)] = session_uuid
            
            logger.info(f"🎤 {member.display_name} joined voice channel {channel.name} (Session: {session_uuid[:8]})")
            
        except Exception as e:
            logger.error(f"Error in handle_voice_join: {e}", exc_info=True)
    
    async def handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """음성 채널 퇴장 처리"""
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            # 활성 세션 조회
            session_key = (guild_id, user_id)
            session_uuid = self.active_sessions.get(session_key)
            
            if not session_uuid:
                # DB에서 조회 시도
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if session_uuid:
                # 세션 종료 및 시간 계산
                duration = await self.db.end_voice_session(session_uuid)
                
                # 메모리 캐시에서 제거
                self.active_sessions.pop(session_key, None)
                
                # 파트너 조회 (if 문 밖으로 이동)
                users_in_channel = await self.db.get_users_in_channel(guild_id, str(channel.id))
                partner_ids = [u['user_id'] for u in users_in_channel if u['user_id'] != user_id]
                
                # 관계 시간 및 EXP는 항상 업데이트
                await self._update_relationships_for_session(
                    guild_id, user_id, str(channel.id), duration
                )
                await self._award_exp_for_session(
                    guild_id, user_id, duration, partner_ids, settings
                )
                
                # 최소 체류 시간 체크 (로그 구분용)
                min_minutes = settings['min_session_minutes']
                if duration >= min_minutes * 60:
                    logger.info(f"✅ {member.display_name} left voice channel (Duration: {duration//60}m {duration%60}s)")
                else:
                    logger.info(f"⏭️ {member.display_name} left voice channel (Short session: {duration//60}m {duration%60}s, but recorded)")
            
        except Exception as e:
            logger.error(f"Error in handle_voice_leave: {e}", exc_info=True)
    
    async def handle_voice_move(self, member: discord.Member, before: discord.VoiceChannel, after: discord.VoiceChannel):
        """음성 채널 이동 처리"""
        try:
            # 이전 채널 퇴장 처리
            await self.handle_voice_leave(member, before)
            
            # 새 채널 입장 처리
            await self.handle_voice_join(member, after)
            
        except Exception as e:
            logger.error(f"Error in handle_voice_move: {e}", exc_info=True)
    
    async def handle_mute_change(self, member: discord.Member, was_muted: bool, is_muted: bool):
        """음소거 상태 변경 처리"""
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled'] or not settings['check_mute_status']:
                return
            
            # 활성 세션 조회
            session_key = (guild_id, user_id)
            session_uuid = self.active_sessions.get(session_key)
            
            if session_uuid:
                await self.db.update_session_mute_status(session_uuid, is_muted)
                logger.info(f"🔇 {member.display_name} mute status: {is_muted}")
        
        except Exception as e:
            logger.error(f"Error in handle_mute_change: {e}", exc_info=True)
    
    async def _update_relationships_for_session(self, guild_id: str, user_id: str, channel_id: str, duration: int):
        """세션 종료 시 해당 유저와 함께 있던 모든 유저와의 관계 시간 업데이트"""
        try:
            # 같은 채널에 있던 다른 유저들 조회
            users_in_channel = await self.db.get_users_in_channel(guild_id, channel_id)
            
            # 본인 제외
            partners = [u for u in users_in_channel if u['user_id'] != user_id]
            
            if not partners:
                logger.debug(f"No partners found for user {user_id} in channel {channel_id}")
                return
            
            guild = self.bot.get_guild(int(guild_id))
            
            # 각 파트너와의 관계 시간 업데이트
            for partner in partners:
                partner_id = partner['user_id']

                # 이전 관계 시간 조회 (마일스톤 체크용)
                old_relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
                old_seconds = old_relationship['total_time_seconds'] if old_relationship else 0
                old_hours = old_seconds / 3600.0
                
                # 관계 시간 업데이트 (duration 초만큼)
                await self.db.update_relationship_time(
                    guild_id, user_id, partner_id, duration
                )

                # 새로운 관계 시간 조회
                new_relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
                new_seconds = new_relationship['total_time_seconds'] if new_relationship else 0
                new_hours = new_seconds / 3600.0

                # 마일스톤 체크 및 알림
                if guild:
                    await self.notification_manager.check_and_send_milestone_notifications(
                        guild, user_id, partner_id, old_hours, new_hours
                    )
                
                logger.debug(f"Updated relationship: {user_id} <-> {partner_id} (+{duration}s)")
            
            logger.info(f"📊 Updated {len(partners)} relationships for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error updating relationships: {e}", exc_info=True)
    
    @tasks.loop(minutes=1)
    async def relationship_update_task(self):
        """
        백그라운드 태스크: 1분마다 활성 세션의 관계 시간 업데이트
        현재 함께 있는 유저들 간의 시간을 실시간으로 누적
        """
        try:
            import random
            if random.randint(1, 60) == 1:  # 약 1시간에 1번
                self.notification_manager.cleanup_old_notifications()

            if not self.active_sessions:
                return
            
            # 길드별로 그룹화
            guilds_to_check: Set[str] = set()
            for (guild_id, _) in self.active_sessions.keys():
                guilds_to_check.add(guild_id)
            
            for guild_id in guilds_to_check:
                # 설정 확인
                settings = await self.db.get_voice_level_settings(guild_id)
                if not settings['enabled']:
                    continue
                
                # 해당 길드의 활성 세션 수집
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                
                # 음성 채널별로 그룹화
                channels_users: Dict[str, List[str]] = {}
                
                for voice_channel in guild.voice_channels:
                    channel_id = str(voice_channel.id)
                    users_in_channel = []
                    
                    for member in voice_channel.members:
                        if member.bot:
                            continue
                        
                        user_id = str(member.id)
                        session_key = (guild_id, user_id)
                        
                        if session_key in self.active_sessions:
                            # 음소거 체크
                            if settings['check_mute_status'] and member.voice and member.voice.self_mute:
                                continue  # 음소거 유저는 제외
                            
                            users_in_channel.append(user_id)
                    
                    if len(users_in_channel) >= 2:
                        channels_users[channel_id] = users_in_channel
                
                # 각 채널의 유저 쌍에 대해 60초 누적
                for channel_id, users in channels_users.items():
                    await self._update_channel_relationships(guild_id, users, 60)

                    for user_id in users:
                        partner_ids = [uid for uid in users if uid != user_id]
                        await self._award_exp_for_session(
                            guild_id, user_id, 60, partner_ids, settings
                        )
                    logger.debug(f"Updated {len(users)} users in channel {channel_id}")
        
        except Exception as e:
            logger.error(f"Error in relationship_update_task: {e}", exc_info=True)
    
    async def _update_channel_relationships(self, guild_id: str, user_ids: List[str], seconds: int):
        try:
            # Guild 객체 조회
            guild = self.bot.get_guild(int(guild_id))
            
            # 모든 유저 쌍(pair) 생성
            for i in range(len(user_ids)):
                for j in range(i + 1, len(user_ids)):
                    user1_id = user_ids[i]
                    user2_id = user_ids[j]
                    
                    # 이전 관계 시간 조회
                    old_relationship = await self.db.get_relationship(guild_id, user1_id, user2_id)
                    old_seconds = old_relationship['total_time_seconds'] if old_relationship else 0
                    old_hours = old_seconds / 3600.0
                    
                    # 관계 시간 업데이트
                    await self.db.update_relationship_time(
                        guild_id, user1_id, user2_id, seconds
                    )
                    
                    # 새로운 관계 시간 조회
                    new_relationship = await self.db.get_relationship(guild_id, user1_id, user2_id)
                    new_seconds = new_relationship['total_time_seconds'] if new_relationship else 0
                    new_hours = new_seconds / 3600.0
                    
                    # 마일스톤 체크 및 알림
                    if guild:
                        await self.notification_manager.check_and_send_milestone_notifications(
                            guild, user1_id, user2_id, old_hours, new_hours
                        )
        
        except Exception as e:
            logger.error(f"Error updating channel relationships: {e}", exc_info=True)

    async def _award_exp_for_session(
        self,
        guild_id: str,
        user_id: str,
        duration_seconds: int,
        partner_ids: List[str],
        settings: Dict
    ):
        """
        세션 종료 시 EXP 계산 및 지급
        
        Args:
            guild_id: 서버 ID
            user_id: 유저 ID
            duration_seconds: 체류 시간 (초)
            partner_ids: 함께 있던 파트너들
            settings: 서버 설정
        """
        try:
            # 파트너가 없으면 exp 없음
            if not partner_ids:
                logger.debug(f"No exp awarded to {user_id}: no partners")
                return
            
            # EXP 계산
            base_exp_per_minute = settings.get('base_exp_per_minute', 10.0)
            
            exp_gained, exp_details = await self.exp_calculator.calculate_exp_for_session(
                guild_id=guild_id,
                user_id=user_id,
                duration_seconds=duration_seconds,
                partner_ids=partner_ids,
                base_exp_per_minute=base_exp_per_minute
            )
            
            if exp_gained <= 0:
                logger.debug(f"No exp gained for {user_id}: {exp_details.get('reason', 'calculated 0')}")
                return
            
            # 레벨업 체크 및 EXP 추가
            levelup_result = await self.exp_calculator.add_exp_and_check_levelup(
                guild_id, user_id, exp_gained
            )
            
            # 플레이 시간 업데이트
            await self.db.update_user_play_time(guild_id, user_id, duration_seconds)
            
            # 고유 파트너 수 업데이트
            await self.db.update_unique_partners_count(guild_id, user_id)
            
            # 레벨업 알림
            if levelup_result['leveled_up']:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        # 통계 조회
                        user_level = await self.db.get_user_level(guild_id, user_id)
                        total_play_hours = user_level['total_play_time_seconds'] // 3600
                        unique_partners = user_level['unique_partners_count']
                        
                        # 레벨업 알림 발송
                        await self.notification_manager.send_levelup_notification(
                            guild=guild,
                            member=member,
                            old_level=levelup_result['old_level'],
                            new_level=levelup_result['new_level'],
                            total_exp=user_level['total_exp'],
                            total_play_hours=total_play_hours,
                            unique_partners=unique_partners
                        )
                
                logger.info(
                    f"🎉 {user_id} leveled up! "
                    f"Lv {levelup_result['old_level']} → Lv {levelup_result['new_level']} "
                    f"(+{exp_gained} exp)"
                )
            else:
                logger.info(
                    f"💎 {user_id} gained {exp_gained} exp "
                    f"(Lv {levelup_result['new_level']}: {levelup_result['current_exp']} exp)"
                )
                        
        except Exception as e:
            logger.error(f"Error awarding exp: {e}", exc_info=True)
    
    @relationship_update_task.before_loop
    async def before_relationship_update_task(self):
        """태스크 시작 전 대기"""
        await self.bot.wait_until_ready()
    
    def stop(self):
        """추적 시스템 중지"""
        if self.relationship_update_task.is_running():
            self.relationship_update_task.cancel()
        logger.info("VoiceLevelTracker stopped")