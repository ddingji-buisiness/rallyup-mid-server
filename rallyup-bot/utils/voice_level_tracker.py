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
    """
    음성 채널 활동 추적 및 관계 시간 누적
    
    ✅ 수정 사항 (2025-10-12):
    - 플레이 시간과 EXP는 세션 종료 시 단 한 번만 지급
    - 백그라운드 태스크는 관계 시간만 업데이트
    - 음소거 전환 시 부분 정산 제거
    """
    
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.exp_calculator = VoiceExpCalculator(self.db)
        self.active_sessions: Dict[Tuple[str, str], str] = {}
        self.notification_manager = VoiceNotificationManager(bot, self.db)
        self.relationship_update_task.start()
        logger.info("✅ VoiceLevelTracker initialized (fixed version)")
    
    async def handle_voice_join(self, member: discord.Member, channel: discord.VoiceChannel):
        """음성 채널 입장 처리"""
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            channel_id = str(channel.id)
            
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            user_level = await self.db.get_user_level(guild_id, user_id)
            if not user_level:
                await self.db.create_user_level(guild_id, user_id)
                logger.info(f"✅ Created user_level for {member.display_name}")
            
            is_muted = member.voice.self_mute if member.voice else False
            is_screen_sharing = member.voice.self_stream if member.voice else False

            session_uuid = await self.db.create_voice_session(
                guild_id, user_id, channel_id, is_muted, is_screen_sharing 
            )
            
            self.active_sessions[(guild_id, user_id)] = session_uuid

            users_in_channel = await self.db.get_users_in_channel(guild_id, channel_id)
            partner_ids = [u['user_id'] for u in users_in_channel if u['user_id'] != user_id]

            if partner_ids:
                # 내 세션에 파트너들 추가
                await self.db.add_session_partners(session_uuid, partner_ids)
                
                # 기존 세션들에도 나를 파트너로 추가
                for partner_id in partner_ids:
                    partner_session = await self.db.get_active_session(guild_id, partner_id)
                    if partner_session:
                        await self.db.add_session_partner(
                            partner_session['session_uuid'], 
                            user_id
                        )

            status = []
            if is_muted:
                status.append("음소거")
            if is_screen_sharing:
                status.append("화면공유")

            status_text = f" ({', '.join(status)})" if status else ""
            logger.info(f"🎤 {member.display_name} joined voice channel{status_text}")
                        
        except Exception as e:
            logger.error(f"Error in handle_voice_join: {e}", exc_info=True)

    async def handle_screen_share_change(
        self, 
        member: discord.Member, 
        was_screen_sharing: bool, 
        is_screen_sharing: bool
    ):
        """
        화면 공유 상태 변경 처리
        
        ✅ 음소거와 동일한 패턴으로 상태만 기록
        """
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled'] or not settings.get('screen_share_bonus_enabled', True):
                return
            
            session_key = (guild_id, user_id)
            session_uuid = self.active_sessions.get(session_key)
            
            if not session_uuid:
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if not session_uuid:
                return
            
            # ✅ 화면 공유 상태 업데이트 (음소거와 동일한 패턴)
            await self.db.update_session_screen_share_status(session_uuid, is_screen_sharing)
            
            status_text = "화면 공유 시작" if is_screen_sharing else "화면 공유 종료"
            logger.info(f"🖥️ {member.display_name} {status_text}")
        
        except Exception as e:
            logger.error(f"Error in handle_screen_share_change: {e}", exc_info=True)
    
    async def handle_voice_leave(self, member: discord.Member, channel: discord.VoiceChannel):
        """
        음성 채널 퇴장 처리 (화면 공유 시간 포함)
        
        ✅ 핵심: 세션 종료 전에 파트너를 먼저 조회!
        """
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                return
            
            session_key = (guild_id, user_id)
            session_uuid = self.active_sessions.get(session_key)
            
            if not session_uuid:
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if not session_uuid:
                return

            partner_ids = await self.db.get_session_partners(session_uuid)
            
            # 세션 종료 및 시간 계산
            total_duration, active_duration, screen_share_duration = \
                await self.db.end_voice_session_with_screen_share(session_uuid)
            
            # 메모리 캐시에서 제거
            self.active_sessions.pop(session_key, None)
            
            # EXP + 플레이 시간 + 화면 공유 시간 지급
            await self._award_exp_for_session(
                guild_id, user_id, active_duration, screen_share_duration,
                partner_ids, settings
            )
            
            logger.info(
                f"✅ {member.display_name} left voice channel "
                f"(Total: {total_duration//60}m, Active: {active_duration//60}m, "
                f"ScreenShare: {screen_share_duration//60}m)"
            )
        
        except Exception as e:
            logger.error(f"Error in handle_voice_leave: {e}", exc_info=True)
    
    async def handle_voice_move(self, member: discord.Member, before: discord.VoiceChannel, after: discord.VoiceChannel):
        """음성 채널 이동 처리"""
        try:
            await self.handle_voice_leave(member, before)
            await self.handle_voice_join(member, after)
            
        except Exception as e:
            logger.error(f"Error in handle_voice_move: {e}", exc_info=True)
    
    async def handle_mute_change(self, member: discord.Member, was_muted: bool, is_muted: bool):
        """
        음소거 상태 변경 처리
        
        ✅ 수정: 부분 시간 정산 제거! 음소거 상태만 기록합니다.
        실제 시간 계산은 세션 종료 시 end_voice_session_with_mute에서 일괄 처리됩니다.
        """
        try:
            if member.bot:
                return
            
            guild_id = str(member.guild.id)
            user_id = str(member.id)
            
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled'] or not settings['check_mute_status']:
                return
            
            session_key = (guild_id, user_id)
            session_uuid = self.active_sessions.get(session_key)
            
            if not session_uuid:
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if not session_uuid:
                return
            
            # ✅ 음소거 상태만 업데이트 (시간 계산은 나중에!)
            await self.db.update_session_mute_status_with_time(session_uuid, is_muted)
            
            status_text = "음소거" if is_muted else "음소거 해제"
            logger.info(f"🔇 {member.display_name} {status_text}")
        
        except Exception as e:
            logger.error(f"Error in handle_mute_change: {e}", exc_info=True)

    async def _update_relationships_for_session(self, guild_id: str, user_id: str, channel_id: str, duration: int):
        """
        세션 종료 시 해당 유저와 함께 있던 모든 유저와의 관계 시간 업데이트
        
        ✅ 수정: 관계 시간만 업데이트! EXP/플레이 시간은 _award_exp_for_session에서 처리
        """
        try:
            users_in_channel = await self.db.get_users_in_channel(guild_id, channel_id)
            partners = [u for u in users_in_channel if u['user_id'] != user_id]
            
            if not partners:
                logger.debug(f"No partners found for user {user_id} in channel {channel_id}")
                return
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            total_users = len(partners) + 1
            
            # ✅ 관계 시간만 업데이트
            for partner in partners:
                partner_id = partner['user_id']
                
                await self.db.update_relationship_time(
                    guild_id, user_id, partner_id, duration
                )
                
                logger.debug(f"Updated relationship: {user_id} <-> {partner_id} (+{duration}s)")
            
            logger.info(f"📊 Updated {len(partners)} relationships for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error updating relationships: {e}", exc_info=True)
    
    @tasks.loop(minutes=1)
    async def relationship_update_task(self):
        """
        백그라운드 태스크: 1분마다 활성 세션의 관계 시간 업데이트
        
        ✅ 수정: 관계 시간만 업데이트! 플레이 시간과 EXP는 세션 종료 시에만!
        """
        try:
            import random
            if random.randint(1, 60) == 1:
                self.notification_manager.cleanup_old_notifications()

            if not self.active_sessions:
                return
            
            guilds_to_check: Set[str] = set()
            for (guild_id, _) in self.active_sessions.keys():
                guilds_to_check.add(guild_id)
            
            for guild_id in guilds_to_check:
                settings = await self.db.get_voice_level_settings(guild_id)
                if not settings['enabled']:
                    continue
                
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue
                
                channels_users: Dict[str, List[str]] = {}
                solo_users: List[str] = []
                
                for voice_channel in guild.voice_channels:
                    channel_id = str(voice_channel.id)
                    users_in_channel = []
                    
                    for member in voice_channel.members:
                        if member.bot:
                            continue
                        
                        user_id = str(member.id)
                        session_key = (guild_id, user_id)
                        
                        if session_key in self.active_sessions:
                            if settings['check_mute_status'] and member.voice and member.voice.self_mute:
                                continue
                            
                            users_in_channel.append(user_id)
                    
                    if len(users_in_channel) == 1:
                        solo_users.append(users_in_channel[0])
                    elif len(users_in_channel) >= 2:
                        channels_users[channel_id] = users_in_channel
                
                # 혼자 있는 유저 표시
                for user_id in solo_users:
                    session_key = (guild_id, user_id)
                    session_uuid = self.active_sessions.get(session_key)
                    if session_uuid:
                        await self.db.mark_session_as_solo(session_uuid)
                        logger.debug(f"👤 User {user_id} is solo in voice channel")
                
                # ✅ 관계 시간만 배치 업데이트
                for channel_id, users in channels_users.items():
                    for user_id in users:
                        session_key = (guild_id, user_id)
                        session_uuid = self.active_sessions.get(session_key)
                        if session_uuid:
                            await self.db.mark_session_as_active_with_partners(session_uuid)
                    
                    # ✅ 관계 시간만 업데이트 (EXP/플레이 시간은 절대 추가 안 함!)
                    await self._update_channel_relationships_batch(guild_id, users, 60)
                    
                    logger.debug(f"✅ Updated relationships for {len(users)} users in channel {channel_id}")
        
        except Exception as e:
            logger.error(f"Error in relationship_update_task: {e}", exc_info=True)

    async def _update_channel_relationships_batch(
        self, 
        guild_id: str, 
        user_ids: List[str], 
        seconds: int
    ):
        """
        채널의 모든 관계를 배치로 업데이트 (성능 최적화)
        
        ✅ 수정: 관계 시간만 업데이트! EXP/플레이 시간은 절대 업데이트하지 않음!
        """
        try:
            if len(user_ids) < 2:
                return
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            # 모든 페어 생성
            pairs = []
            for i in range(len(user_ids)):
                for j in range(i + 1, len(user_ids)):
                    user1_id = user_ids[i]
                    user2_id = user_ids[j]
                    if user1_id > user2_id:
                        user1_id, user2_id = user2_id, user1_id
                    pairs.append((user1_id, user2_id))
            
            logger.debug(f"📊 Processing {len(pairs)} pairs in batch")
            
            # 기존 관계 정보 한 번에 조회
            old_relationships = await self.db.get_relationships_for_pairs(guild_id, pairs)
            
            # 배치 업데이트 준비
            updates = []
            
            for user1_id, user2_id in pairs:
                updates.append((guild_id, user1_id, user2_id, seconds))
            
            # ✅ 단일 트랜잭션으로 모든 관계 업데이트
            await self.db.batch_update_relationships(updates)
            
            logger.info(f"✅ Batch updated {len(updates)} relationships")
            
            # ❌ 절대 추가하지 않음: EXP/플레이 시간 업데이트 코드!
            # 이 주석을 지우지 마세요 - 실수 방지용
        
        except Exception as e:
            logger.error(f"Error in _update_channel_relationships_batch: {e}", exc_info=True)

    async def _award_exp_for_session(
        self,
        guild_id: str,
        user_id: str,
        duration_seconds: int,
        screen_share_seconds: int,
        partner_ids: List[str],
        settings: Dict
    ):
        """
        세션에 대한 EXP 계산 및 지급 (화면 공유 보너스 포함)
        
        ✅ 중요: 이 함수는 handle_voice_leave에서만 호출됩니다!
        """
        try:
            if not partner_ids:
                logger.debug(f"No exp awarded to {user_id}: no partners")
                return
            
            base_exp_per_minute = settings.get('base_exp_per_minute', 10.0)
            screen_share_bonus = settings.get('screen_share_bonus_enabled', True)
            screen_share_multiplier = settings.get('screen_share_multiplier', 1.5)

            if screen_share_seconds > duration_seconds:
                logger.warning(
                    f"⚠️ {user_id}: Screen share time ({screen_share_seconds}s) exceeds "
                    f"active time ({duration_seconds}s). User was likely muted while sharing screen. "
                    f"Capping screen share time to active time."
                )
                screen_share_seconds = duration_seconds
            
            # 일반 시간과 화면 공유 시간 분리 계산
            normal_seconds = duration_seconds - screen_share_seconds

            normal_seconds = max(0, normal_seconds)
            
            # 일반 시간 EXP
            normal_exp, normal_details = await self.exp_calculator.calculate_exp_for_session(
                guild_id=guild_id,
                user_id=user_id,
                duration_seconds=normal_seconds,
                partner_ids=partner_ids,
                base_exp_per_minute=base_exp_per_minute
            )
            
            # 화면 공유 시간 EXP (보너스 적용)
            screen_share_exp = 0
            if screen_share_bonus and screen_share_seconds > 0:
                ss_exp, ss_details = await self.exp_calculator.calculate_exp_for_session(
                    guild_id=guild_id,
                    user_id=user_id,
                    duration_seconds=screen_share_seconds,
                    partner_ids=partner_ids,
                    base_exp_per_minute=base_exp_per_minute * screen_share_multiplier
                )
                screen_share_exp = ss_exp
            
            # 총 EXP
            total_exp = normal_exp + screen_share_exp
            
            if total_exp <= 0:
                logger.debug(f"No exp gained for {user_id}")
                return
            
            # EXP 추가 및 레벨업 체크
            levelup_result = await self.exp_calculator.add_exp_and_check_levelup(
                guild_id, user_id, total_exp
            )
            
            # 플레이 시간 업데이트
            await self.db.update_user_play_time(guild_id, user_id, duration_seconds)
            
            # 화면 공유 시간 업데이트
            if screen_share_seconds > 0:
                await self.db.update_user_screen_share_time(guild_id, user_id, screen_share_seconds)
            
            # 고유 파트너 수 업데이트
            await self.db.update_unique_partners_count(guild_id, user_id)
            
            # 레벨업 알림
            if levelup_result['leveled_up']:
                guild = self.bot.get_guild(int(guild_id))
                if guild:
                    member = guild.get_member(int(user_id))
                    if member:
                        user_level = await self.db.get_user_level(guild_id, user_id)
                        total_play_hours = user_level['total_play_time_seconds'] // 3600
                        unique_partners = user_level['unique_partners_count']
                        
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
                    f"(+{total_exp} exp, {screen_share_exp} from screen share)"
                )
            else:
                logger.info(
                    f"💎 {user_id} gained {total_exp} exp "
                    f"(Normal: {normal_exp}, ScreenShare: {screen_share_exp})"
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

    async def restore_voice_sessions(self):
        """
        봇 재시작 시 활성 음성 세션 복구
        현재 음성 채널에 있는 유저들의 세션 자동 생성
        """
        try:
            restored_count = 0
            
            for guild in self.bot.guilds:
                settings = await self.db.get_voice_level_settings(str(guild.id))
                if not settings['enabled']:
                    continue
                
                for voice_channel in guild.voice_channels:
                    # 채널에 있는 모든 멤버 ID 수집 (봇 제외)
                    members_in_channel = [m for m in voice_channel.members if not m.bot]
                    
                    for member in members_in_channel:
                        guild_id = str(guild.id)
                        user_id = str(member.id)
                        
                        # 기존 세션 확인
                        existing_session = await self.db.get_active_session(guild_id, user_id)
                        if existing_session:
                            continue
                        
                        # 유저 레벨 확인/생성
                        user_level = await self.db.get_user_level(guild_id, user_id)
                        if not user_level:
                            await self.db.create_user_level(guild_id, user_id)
                        
                        is_muted = member.voice.self_mute if member.voice else False
                        is_screen_sharing = member.voice.self_stream if member.voice else False
                        
                        # 세션 생성
                        session_uuid = await self.db.create_voice_session(
                            guild_id, user_id, str(voice_channel.id), 
                            is_muted, is_screen_sharing
                        )
                        
                        self.active_sessions[(guild_id, user_id)] = session_uuid
                        restored_count += 1
                    
                    # 같은 채널 멤버들을 서로 파트너로 등록
                    for i, member in enumerate(members_in_channel):
                        user_id = str(member.id)
                        session_uuid = self.active_sessions.get((str(guild.id), user_id))
                        
                        if session_uuid:
                            # 자신을 제외한 다른 멤버들
                            partner_ids = [
                                str(other.id) for other in members_in_channel 
                                if other.id != member.id
                            ]
                            
                            if partner_ids:
                                await self.db.add_session_partners(session_uuid, partner_ids)
            
            if restored_count > 0:
                logger.info(f"🎤 Restored {restored_count} voice sessions")
        
        except Exception as e:
            logger.error(f"Error restoring voice sessions: {e}", exc_info=True)