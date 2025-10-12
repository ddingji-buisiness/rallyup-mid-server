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
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if session_uuid:
                # ✅ 세션 종료 및 시간 계산 (음소거 시간 반영)
                total_duration, active_duration = await self.db.end_voice_session_with_mute(session_uuid)
                
                # 메모리 캐시에서 제거
                self.active_sessions.pop(session_key, None)
                
                # 파트너 조회
                users_in_channel = await self.db.get_users_in_channel(guild_id, str(channel.id))
                partner_ids = [u['user_id'] for u in users_in_channel if u['user_id'] != user_id]
                
                # ✅ 활성 시간(active_duration) 사용
                # 관계 시간 및 EXP는 항상 업데이트 (활성 시간만)
                await self._update_relationships_for_session(
                    guild_id, user_id, str(channel.id), active_duration
                )
                await self._award_exp_for_session(
                    guild_id, user_id, active_duration, partner_ids, settings
                )
                
                # 최소 체류 시간 체크 (로그 구분용)
                min_minutes = settings['min_session_minutes']
                if active_duration >= min_minutes * 60:
                    logger.info(
                        f"✅ {member.display_name} left voice channel "
                        f"(Total: {total_duration//60}m {total_duration%60}s, "
                        f"Active: {active_duration//60}m {active_duration%60}s)"
                    )
                else:
                    logger.info(
                        f"⏭️ {member.display_name} left voice channel "
                        f"(Short session - Total: {total_duration//60}m {total_duration%60}s, "
                        f"Active: {active_duration//60}m {active_duration%60}s, but recorded)"
                    )
            
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
        """
        음소거 상태 변경 처리 + 즉시 시간 정산
        
        개선사항: 음소거 전환 시 그 시점까지의 시간을 즉시 정산하여
                중간 시간 손실 방지
        """
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
            
            if not session_uuid:
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data:
                    session_uuid = session_data['session_uuid']
            
            if not session_uuid:
                return
            
            if was_muted and not is_muted:
                logger.info(f"🔊 {member.display_name} unmuted - settling previous active period")
                
                # 마지막 음소거 해제 이후 경과 시간 계산
                session_data = await self.db.get_active_session(guild_id, user_id)
                if session_data and session_data.get('mute_started_at'):
                    # 음소거 시작 시점부터 지금까지의 시간은 이미 total_muted_seconds에 반영됨
                    pass
                
                # 음소거 해제 전까지의 활성 시간 정산
                elapsed_seconds = await self.db.get_session_elapsed_seconds(session_uuid)
                
                if elapsed_seconds > 0:
                    # 현재 채널의 다른 유저들과 관계 시간 업데이트
                    channel_id = session_data['channel_id'] if session_data else None
                    if channel_id:
                        users_in_channel = await self.db.get_users_in_channel(guild_id, channel_id)
                        partner_ids = [u['user_id'] for u in users_in_channel if u['user_id'] != user_id]
                        
                        if partner_ids:
                            # 부분 시간 정산
                            await self._settle_partial_time(
                                guild_id, user_id, channel_id, elapsed_seconds, partner_ids, settings
                            )
            
            # 음소거 상태 업데이트
            await self.db.update_session_mute_status_with_time(session_uuid, is_muted)
            
            status_text = "음소거" if is_muted else "음소거 해제"
            logger.info(f"🔇 {member.display_name} {status_text}")
        
        except Exception as e:
            logger.error(f"Error in handle_mute_change: {e}", exc_info=True)

    async def _settle_partial_time(
        self,
        guild_id: str,
        user_id: str,
        channel_id: str,
        elapsed_seconds: int,
        partner_ids: list,
        settings: dict
    ):
        """
        부분 시간 정산 (음소거 전환 시점에 호출)
        
        Args:
            guild_id: 서버 ID
            user_id: 유저 ID  
            channel_id: 채널 ID
            elapsed_seconds: 정산할 시간 (초)
            partner_ids: 함께 있던 파트너들
            settings: 서버 설정
        """
        try:
            # 관계 시간 업데이트
            await self._update_relationships_for_session(
                guild_id, user_id, channel_id, elapsed_seconds
            )
            
            # EXP 지급
            await self._award_exp_for_session(
                guild_id, user_id, elapsed_seconds, partner_ids, settings
            )
            
            logger.info(f"💰 Settled {elapsed_seconds}s for user {user_id}")
        
        except Exception as e:
            logger.error(f"Error settling partial time: {e}", exc_info=True)
    

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
            
            # Guild 객체 조회 (알림용)
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            # 총 인원 수 (본인 포함)
            total_users = len(partners) + 1
            
            # 마일스톤 체크용 데이터 수집
            milestone_data = []  # [(user_id, partner_id, old_hours, new_hours, achieved_milestones)]
            
            # 각 파트너와의 관계 시간 업데이트
            for partner in partners:
                partner_id = partner['user_id']
                
                # 이전 관계 시간 조회
                old_relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
                old_seconds = old_relationship['total_time_seconds'] if old_relationship else 0
                old_hours = old_seconds / 3600.0
                
                # 관계 시간 업데이트
                await self.db.update_relationship_time(
                    guild_id, user_id, partner_id, duration
                )
                
                # 새로운 관계 시간 조회
                new_relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
                new_seconds = new_relationship['total_time_seconds'] if new_relationship else 0
                new_hours = new_seconds / 3600.0
                
                # 달성한 마일스톤 찾기
                achieved_milestones = []
                for milestone in self.notification_manager.RELATIONSHIP_MILESTONES:
                    if old_hours < milestone <= new_hours:
                        achieved_milestones.append(milestone)
                
                milestone_data.append((user_id, partner_id, old_hours, new_hours, achieved_milestones))
                
                logger.debug(f"Updated relationship: {user_id} <-> {partner_id} (+{duration}s)")
            
            # ✅ 알림 발송 로직 (하이브리드 방식)
            if total_users == 2:
                # ===== 2명만 있을 때 =====
                for user_id, partner_id, old_hours, new_hours, achieved_milestones in milestone_data:
                    if achieved_milestones:
                        user1 = guild.get_member(int(user_id))
                        user2 = guild.get_member(int(partner_id))
                        
                        if user1 and user2:
                            for milestone in achieved_milestones:
                                if self.notification_manager.is_special_milestone(milestone):
                                    # 특별 마일스톤(50h+): Embed
                                    await self.notification_manager.send_special_milestone_embed(
                                        guild, user1, user2, milestone, new_hours
                                    )
                                else:
                                    # 일반 마일스톤: 텍스트 (스마트 업데이트)
                                    await self.notification_manager.add_milestone_event(
                                        guild, [user1, user2], milestone, channel_id
                                    )
            
            elif total_users >= 3:
                # ===== 3명 이상 있을 때 =====
                
                # 모든 달성된 마일스톤 수집
                all_achieved = set()
                for _, _, _, _, achieved in milestone_data:
                    all_achieved.update(achieved)
                
                # 일반 마일스톤과 특별 마일스톤 분리
                regular_milestones = [m for m in all_achieved if not self.notification_manager.is_special_milestone(m)]
                special_milestones = [m for m in all_achieved if self.notification_manager.is_special_milestone(m)]
                
                # 멤버 리스트 생성
                member_list = []
                member_list.append(guild.get_member(int(user_id)))
                for partner in partners:
                    member = guild.get_member(int(partner['user_id']))
                    if member:
                        member_list.append(member)
                
                # None 제거
                member_list = [m for m in member_list if m is not None]
                
                # 1) 일반 마일스톤: 그룹 텍스트 알림 (스마트 업데이트)
                if regular_milestones and member_list:
                    for milestone in sorted(regular_milestones):
                        await self.notification_manager.add_milestone_event(
                            guild, member_list, milestone, channel_id
                        )
                
                # 2) 특별 마일스톤: 개별 Embed (기존 방식)
                if special_milestones:
                    for user_id, partner_id, _, new_hours, achieved in milestone_data:
                        special_achieved = [m for m in achieved if self.notification_manager.is_special_milestone(m)]
                        
                        if special_achieved:
                            user1 = guild.get_member(int(user_id))
                            user2 = guild.get_member(int(partner_id))
                            
                            if user1 and user2:
                                for milestone in special_achieved:
                                    await self.notification_manager.send_special_milestone_embed(
                                        guild, user1, user2, milestone, new_hours
                                    )
            
            logger.info(f"📊 Updated {len(partners)} relationships for user {user_id} (Total users: {total_users})")
        
        except Exception as e:
            logger.error(f"Error updating relationships: {e}", exc_info=True)
    
    @tasks.loop(minutes=1)
    async def relationship_update_task(self):
        """
        백그라운드 태스크: 1분마다 활성 세션의 관계 시간 업데이트
        
        개선사항:
        1. 혼자 있는 유저는 solo 상태로 표시
        2. 대규모 채널은 배치 업데이트
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
                            # 음소거 체크
                            if settings['check_mute_status'] and member.voice and member.voice.self_mute:
                                continue
                            
                            users_in_channel.append(user_id)
                    
                    if len(users_in_channel) == 1:
                        solo_users.append(users_in_channel[0])
                    elif len(users_in_channel) >= 2:
                        channels_users[channel_id] = users_in_channel
                
                for user_id in solo_users:
                    session_key = (guild_id, user_id)
                    session_uuid = self.active_sessions.get(session_key)
                    if session_uuid:
                        await self.db.mark_session_as_solo(session_uuid)
                        logger.debug(f"👤 User {user_id} is solo in voice channel")
                
                for channel_id, users in channels_users.items():
                    for user_id in users:
                        session_key = (guild_id, user_id)
                        session_uuid = self.active_sessions.get(session_key)
                        if session_uuid:
                            await self.db.mark_session_as_active_with_partners(session_uuid)
                    
                    await self._update_channel_relationships_batch(guild_id, users, 60)
                    
                    # EXP 지급
                    for user_id in users:
                        partner_ids = [uid for uid in users if uid != user_id]
                        await self._award_exp_for_session(
                            guild_id, user_id, 60, partner_ids, settings
                        )
                    
                    logger.debug(f"✅ Updated {len(users)} users in channel {channel_id}")
        
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
        
        개선사항: 
        - 30명 = 435쌍이어도 단일 트랜잭션으로 처리
        - 기존 관계 정보를 한 번에 조회
        - 마일스톤 체크는 변경된 것만
        - 하이브리드 알림 시스템 적용
        
        Args:
            guild_id: 서버 ID
            user_ids: 채널에 있는 유저 ID 리스트
            seconds: 추가할 시간 (초)
        """
        try:
            if len(user_ids) < 2:
                return
            
            # Guild 객체 조회
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            # 채널 ID 추출
            channel_id = None
            if user_ids:
                session_data = await self.db.get_active_session(guild_id, user_ids[0])
                if session_data:
                    channel_id = session_data['channel_id']
            
            # ✅ 1단계: 모든 페어 생성
            pairs = []
            for i in range(len(user_ids)):
                for j in range(i + 1, len(user_ids)):
                    user1_id = user_ids[i]
                    user2_id = user_ids[j]
                    if user1_id > user2_id:
                        user1_id, user2_id = user2_id, user1_id
                    pairs.append((user1_id, user2_id))
            
            logger.debug(f"📊 Processing {len(pairs)} pairs in batch")
            
            # ✅ 2단계: 기존 관계 정보 한 번에 조회
            old_relationships = await self.db.get_relationships_for_pairs(guild_id, pairs)
            
            # ✅ 3단계: 배치 업데이트 준비
            updates = []
            milestone_data = []  # [(user1_id, user2_id, old_hours, new_hours, achieved_milestones)]
            
            for user1_id, user2_id in pairs:
                # 기존 시간
                old_rel = old_relationships.get((user1_id, user2_id))
                old_seconds = old_rel['total_time_seconds'] if old_rel else 0
                old_hours = old_seconds / 3600.0
                
                # 새로운 시간
                new_seconds = old_seconds + seconds
                new_hours = new_seconds / 3600.0
                
                # 업데이트 목록에 추가
                updates.append((guild_id, user1_id, user2_id, seconds))
                
                # 달성한 마일스톤 찾기
                achieved_milestones = []
                for milestone in self.notification_manager.RELATIONSHIP_MILESTONES:
                    if old_hours < milestone <= new_hours:
                        achieved_milestones.append(milestone)
                
                if achieved_milestones:
                    milestone_data.append((user1_id, user2_id, old_hours, new_hours, achieved_milestones))
            
            # ✅ 4단계: 단일 트랜잭션으로 모든 관계 업데이트
            await self.db.batch_update_relationships(updates)
            
            logger.info(f"✅ Batch updated {len(updates)} relationships in single transaction")
            
            # ✅ 5단계: 알림 발송 (하이브리드 방식)
            total_users = len(user_ids)
            
            if total_users == 2:
                # ===== 2명만 있을 때 =====
                for user1_id, user2_id, old_hours, new_hours, achieved_milestones in milestone_data:
                    if achieved_milestones:
                        user1 = guild.get_member(int(user1_id))
                        user2 = guild.get_member(int(user2_id))
                        
                        if user1 and user2:
                            for milestone in achieved_milestones:
                                if self.notification_manager.is_special_milestone(milestone):
                                    # 특별 마일스톤(50h+): Embed
                                    await self.notification_manager.send_special_milestone_embed(
                                        guild, user1, user2, milestone, new_hours
                                    )
                                else:
                                    # 일반 마일스톤: 텍스트 (스마트 업데이트)
                                    await self.notification_manager.add_milestone_event(
                                        guild, [user1, user2], milestone, channel_id
                                    )
            
            elif total_users >= 3:
                # ===== 3명 이상 있을 때 =====
                
                # 모든 달성된 마일스톤 수집
                all_achieved = set()
                for _, _, _, _, achieved in milestone_data:
                    all_achieved.update(achieved)
                
                # 일반 마일스톤과 특별 마일스톤 분리
                regular_milestones = [m for m in all_achieved if not self.notification_manager.is_special_milestone(m)]
                special_milestones = [m for m in all_achieved if self.notification_manager.is_special_milestone(m)]
                
                # 1) 일반 마일스톤: 그룹 텍스트 알림 (스마트 업데이트)
                if regular_milestones:
                    # 멤버 리스트 생성
                    member_list = []
                    for user_id in user_ids:
                        member = guild.get_member(int(user_id))
                        if member:
                            member_list.append(member)
                    
                    if member_list:
                        # 각 마일스톤별로 그룹 메시지 추가
                        for milestone in sorted(regular_milestones):
                            await self.notification_manager.add_milestone_event(
                                guild, member_list, milestone, channel_id
                            )
                
                # 2) 특별 마일스톤: 개별 Embed (기존 방식)
                if special_milestones:
                    for user1_id, user2_id, _, new_hours, achieved in milestone_data:
                        special_achieved = [m for m in achieved if self.notification_manager.is_special_milestone(m)]
                        
                        if special_achieved:
                            user1 = guild.get_member(int(user1_id))
                            user2 = guild.get_member(int(user2_id))
                            
                            if user1 and user2:
                                for milestone in special_achieved:
                                    await self.notification_manager.send_special_milestone_embed(
                                        guild, user1, user2, milestone, new_hours
                                    )
        
        except Exception as e:
            logger.error(f"Error in _update_channel_relationships_batch: {e}", exc_info=True)

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

    async def restore_voice_sessions(self):
        """
        봇 재시작 시 활성 음성 세션 복구
        현재 음성 채널에 있는 유저들의 세션 자동 생성
        """
        try:
            restored_count = 0
            
            for guild in self.bot.guilds:
                guild_id = str(guild.id)
                
                # 설정 확인
                settings = await self.db.get_voice_level_settings(guild_id)
                if not settings['enabled']:
                    logger.debug(f"Voice level disabled for guild {guild.name}, skipping restore")
                    continue
                
                # 각 음성 채널 확인
                for voice_channel in guild.voice_channels:
                    channel_id = str(voice_channel.id)
                    
                    for member in voice_channel.members:
                        # 봇 제외
                        if member.bot:
                            continue
                        
                        user_id = str(member.id)
                        session_key = (guild_id, user_id)
                        
                        # 이미 메모리에 세션이 있으면 스킵
                        if session_key in self.active_sessions:
                            continue
                        
                        # DB에 활성 세션이 있는지 확인
                        existing_session = await self.db.get_active_session(guild_id, user_id)
                        
                        if existing_session:
                            # 기존 세션 복구
                            session_uuid = existing_session['session_uuid']
                            self.active_sessions[session_key] = session_uuid
                            logger.info(f"🔄 Restored existing session: {member.display_name} (Session: {session_uuid[:8]})")
                            restored_count += 1
                        else:
                            # 새 세션 생성
                            is_muted = member.voice.self_mute if member.voice else False
                            
                            session_uuid = await self.db.create_voice_session(
                                guild_id, user_id, channel_id, is_muted
                            )
                            
                            self.active_sessions[session_key] = session_uuid
                            logger.info(f"🔄 Created new session: {member.display_name} (Session: {session_uuid[:8]})")
                            restored_count += 1
            
            if restored_count > 0:
                logger.info(f"✅ Restored {restored_count} voice session(s) after bot restart")
            else:
                logger.info("ℹ️ No active voice sessions to restore")
        
        except Exception as e:
            logger.error(f"Error restoring voice sessions: {e}", exc_info=True)

    