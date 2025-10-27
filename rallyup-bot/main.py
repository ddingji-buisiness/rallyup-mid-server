import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
import os
from database.database import DatabaseManager
from scheduler.bamboo_scheduler import BambooForestScheduler
from scheduler.recruitment_scheduler import RecruitmentScheduler
from scheduler.scrim_scheduler import ScrimScheduler
from commands.scrim_recruitment import RecruitmentView
from utils.battle_tag_logger import BattleTagLogger
from utils.balancing_session_manager import session_manager
from utils.voice_level_tracker import VoiceLevelTracker

from config.settings import Settings

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RallyUpBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True
        intents.guilds = True
        intents.message_content = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db_manager = DatabaseManager()
        self.bamboo_scheduler = BambooForestScheduler(self)
        self.recruitment_scheduler = None
        self.scrim_scheduler = None
        self.wordle_scheduler = None

        self.korean_api = None
        self.similarity_calc = None
        self.challenge_scheduler = None
        self.challenge_notifier = None
        self._daily_challenge_enabled = False

        self.challenge_engine = None
        self.challenge_event_manager = None
        self._continuous_challenge_enabled = False
        self.battle_tag_logger = None
        self.tier_change_scheduler = None  
        self.voice_level_tracker = None

    async def setup_hook(self):
        """봇 시작시 실행되는 설정"""
        try:
            await self.db_manager.initialize()
            logger.info("데이터베이스 초기화 완료")

            await self.load_commands()

            await self._register_persistent_views()
            logger.info("✅ Persistent Views 등록 완료")

            from utils.battle_tag_logger import BattleTagLogger
            self.battle_tag_logger = BattleTagLogger(self)
            logger.info("배틀태그 로거 초기화 완료")
            
            await self.bamboo_scheduler.start()
            logger.info("대나무숲 스케줄러 시작")

            if not self.voice_level_tracker:
                self.voice_level_tracker = VoiceLevelTracker(self)
                logger.info("음성 레벨 트래커 시작")

            if not self.recruitment_scheduler:
                self.recruitment_scheduler = RecruitmentScheduler(self)
                await self.recruitment_scheduler.start()
                logger.info("내전 모집 스케줄러 시작")

            if not self.scrim_scheduler:
                self.scrim_scheduler = ScrimScheduler(self)
                await self.scrim_scheduler.start()
                logger.info("스크림 스케줄러 시작")

            # 티어 변동 스케줄러 시작
            if not self.tier_change_scheduler:
                from scheduler.tier_change_scheduler import TierChangeScheduler
                self.tier_change_scheduler = TierChangeScheduler(self)
                await self.tier_change_scheduler.start()
                logger.info("티어 변동 감지 스케줄러 시작")

            await self.restore_inquiry_views()
            logger.info("문의 시스템 View 복원 완료")

            try:
                print("슬래시 커맨드 동기화 중...")
                synced = await self.tree.sync()
                logger.info(f"Synced {len(synced)} command(s)")
            except Exception as e:
                logger.error(f"Failed to sync commands: {e}")
                
        except Exception as e:
            logger.error(f"Setup hook failed: {e}")
            raise

    async def load_commands(self):
        """커맨드 로드"""
        commands_to_load = [
            'commands.help',
            'commands.match_result',
            'commands.scrim_session',
            'commands.clan_scrim',
            'commands.user_application',
            'commands.admin_system',
            'commands.bamboo_forest',
            'commands.scrim_recruitment',
            'commands.scrim_result_recording',
            'commands.simple_user_management',
            'commands.inter_guild_scrim',
            'commands.team_balancing',
            'commands.nickname_format_admin',
            'commands.battle_tag_commands',
            'commands.battle_tag_log_admin',
            'commands.team_info',
            'commands.voice_level_admin',
            'commands.voice_level_user',
            'commands.tts_commands',
            'commands.inquiry_system'
        ]

        for command_module in commands_to_load:
            try:
                await self.load_extension(command_module)
                logger.info(f"✅ Loaded: {command_module}")
            except Exception as e:
                logger.error(f"❌ Failed to load {command_module}: {e}")
    
        
        logger.info("Command loading completed")

    async def _load_continuous_challenge_commands(self, command_modules: list):
        """연속형 챌린지 명령어들 로드 (파라미터 포함)"""
        
        for command_module in command_modules:
            try:
                # 모듈 임포트
                module = __import__(command_module, fromlist=['setup'])
                
                await module.setup(
                    self,
                    self.challenge_engine,
                    self.challenge_event_manager
                )
                
                logger.info(f"✅ Loaded continuous challenge command: {command_module}")
                
            except Exception as e:
                logger.error(f"❌ Failed to load continuous challenge command {command_module}: {e}")
                logger.error(f"   Error details: {type(e).__name__}: {str(e)}")
    
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # 봇 상태 설정
        await self.change_presence(
            activity=discord.Game(name="RallyUp 클랜 관리 | /help")
        )

        await session_manager.start_cleanup_task()
        print('✅ 밸런싱 세션 자동 정리 태스크 시작됨')

        # 음성 세션 복구
        if self.voice_level_tracker:
            try:
                await self.voice_level_tracker.restore_voice_sessions()
                logger.info("🔄 음성 세션 복구 완료")
            except Exception as e:
                logger.error(f"❌ 음성 세션 복구 실패: {e}", exc_info=True)

        # 스케줄러 상태 확인
        if self.bamboo_scheduler.running:
            logger.info("대나무숲 스케줄러가 실행중입니다.")
        else:
            logger.warning("대나무숲 스케줄러가 실행되지 않았습니다.")

        if self.recruitment_scheduler and self.recruitment_scheduler.is_running:
            logger.info("내전 모집 스케줄러가 실행 중입니다")
        else:
            logger.warning("내전 모집 스케줄러가 실행되지 않았습니다!")

        if self.scrim_scheduler and self.scrim_scheduler.running:
            logger.info("스크림 스케줄러가 실행 중입니다")
        else:
            logger.warning("스크림 스케줄러가 실행되지 않았습니다!")

        if not hasattr(self, '_consultation_cleanup_task'):
            self._consultation_cleanup_task = asyncio.create_task(
                self._consultation_cleanup_loop()
            )
            logger.info("상담 자동 정리 태스크 시작")

        await self.restore_recruitment_views()

    async def _consultation_cleanup_loop(self):
        """상담 자동 정리 루프 (24시간마다 실행)"""
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                # 72시간 이상 응답 없는 상담 정리
                cleaned = await self.db_manager.cleanup_stale_consultations(hours=72)
                
                if cleaned > 0:
                    logger.info(f"🧹 자동 정리: {cleaned}개 상담 타임아웃")
                
                # 24시간 대기
                await asyncio.sleep(86400)  # 24시간
                
            except Exception as e:
                logger.error(f"❌ 상담 정리 루프 오류: {e}")
                await asyncio.sleep(3600)  # 1시간 후 재시도

    async def _register_persistent_views(self):
        """Persistent Views 등록 (봇 재시작 후에도 작동)"""
        try:
            from commands.inquiry_system import (
                TicketManagementView,
                ThreadDMBridgeView,
                UserReplyView,
                ConsultationRequestView
            )

            # TicketManagementView (티켓 관리)
            self.add_view(TicketManagementView(
                bot=self,
                guild_id="",
                ticket_number="",
                is_anonymous=False,
                user_id=""
            ))
            
            # ThreadDMBridgeView (쓰레드-DM 브리지)
            self.add_view(ThreadDMBridgeView(
                bot=self,
                guild_id="",
                ticket_number="",
                user_id="",
                thread=None
            ))
            
            # UserReplyView (사용자 답장)
            self.add_view(UserReplyView(
                bot=self,
                guild_id="",
                ticket_number="",
                thread_id=""
            ))
            
            # ConsultationResponseView (1:1 상담 수락/거절)
            self.add_view(ConsultationRequestView(
                bot=self,
                ticket_number="",
                user_id="",
                username="",
                guild_id="",
                admin_id="",
                admin_name="",
                category="",
                content="",
                is_urgent=False
            ))
            
            logger.info("📋 문의 시스템 Persistent Views 등록 완료")
            
        except Exception as e:
            logger.error(f"❌ Persistent Views 등록 실패: {e}", exc_info=True)

    async def restore_inquiry_views(self):
        # TicketManagementView는 callback에서 동적으로 처리
        logger.info("✅ 문의 View 복원 완료")

    async def restore_recruitment_views(self):
        try:
            restored_count = 0
            
            for guild in self.guilds:
                try:
                    active_recruitments = await self.db_manager.get_active_recruitments(str(guild.id))
                    logger.info(f"길드 {guild.name}에서 {len(active_recruitments)}개의 활성 모집 발견")
                    for recruitment in active_recruitments:                        
                        if recruitment.get('message_id') and recruitment.get('channel_id'):
                            try:
                                channel = self.get_channel(int(recruitment['channel_id']))
                                if channel:
                                    try:
                                        from commands.scrim_recruitment import RecruitmentView
                                    except ImportError as e:
                                        logger.error(f"RecruitmentView import 실패: {e}")
                                        continue
                                    
                                    view = RecruitmentView(self, recruitment['id'])
                                    
                                    self.add_view(view)
                                    restored_count += 1
                                else:
                                    logger.warning(f"채널을 찾을 수 없음: {recruitment['channel_id']}")
                                    
                            except Exception as e:
                                logger.error(f"개별 recruitment view 복원 실패 {recruitment['id']}: {e}")
                                import traceback
                                logger.error(traceback.format_exc())
                        else:
                            logger.warning(f"message_id 또는 channel_id가 없음: {recruitment['id']}")
                                
                except Exception as e:
                    logger.error(f"길드 {guild.name}의 recruitment view 복원 중 오류: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    
            logger.info(f"✅ {restored_count}개의 Recruitment View가 복원되었습니다.")
            
        except Exception as e:
            logger.error(f"❌ Recruitment View 복원 중 전체 오류: {e}")
            import traceback
            logger.error(traceback.format_exc())

    async def on_member_join(self, member: discord.Member):
        """신규 멤버가 서버에 입장할 때 자동 역할 배정"""
        
        # 봇은 제외
        if member.bot:
            logger.info(f"🤖 Bot joined {member.guild.name}: {member.name} (역할 배정 제외)")
            return
        
        guild_id = str(member.guild.id)
        user_id = str(member.id)
        
        logger.info(f"👋 새로운 멤버 입장: {member.display_name} (ID: {user_id}) in {member.guild.name}")
        
        try:
            # 서버의 신규 멤버 자동 역할 설정 조회
            settings = await self.db_manager.get_new_member_auto_role_settings(guild_id)
            
            # 자동 역할 배정이 비활성화된 경우
            if not settings['enabled']:
                logger.info(f"⏸️ {member.guild.name}: 신규 멤버 자동 역할 배정이 비활성화됨")
                return
            
            # 설정된 역할이 없는 경우
            if not settings['role_id']:
                logger.warning(f"⚠️ {member.guild.name}: 신규 멤버 역할이 설정되지 않음")
                return
            
            # 역할 객체 가져오기
            role = member.guild.get_role(int(settings['role_id']))
            if not role:
                logger.error(f"❌ {member.guild.name}: 설정된 역할(ID: {settings['role_id']})을 찾을 수 없음")
                return
            
            # 봇의 권한 확인
            bot_member = member.guild.get_member(self.user.id)
            if not bot_member:
                logger.error(f"❌ {member.guild.name}: 봇 멤버 정보를 가져올 수 없음")
                return
            
            # 봇이 해당 역할을 배정할 수 있는지 확인
            if role.position >= bot_member.top_role.position:
                logger.error(
                    f"❌ {member.guild.name}: 역할 '{role.name}'이 봇의 최고 역할보다 높음 "
                    f"(역할 위치: {role.position}, 봇 최고 역할: {bot_member.top_role.position})"
                )
                return
            
            # 역할 배정 권한 확인
            if not member.guild.me.guild_permissions.manage_roles:
                logger.error(f"❌ {member.guild.name}: 봇에게 역할 관리 권한이 없음")
                return
            
            # 이미 해당 역할을 가지고 있는지 확인 (안전장치)
            if role in member.roles:
                logger.info(f"ℹ️ {member.display_name}은 이미 '{role.name}' 역할을 보유함")
                return
            
            # 역할 배정 실행
            await member.add_roles(
                role, 
                reason=f"RallyUp 봇 - 신규 멤버 자동 역할 배정"
            )
            
            logger.info(
                f"✅ 역할 배정 성공: {member.display_name} → '{role.name}' "
                f"in {member.guild.name}"
            )
            
        except discord.Forbidden:
            logger.error(
                f"❌ 권한 부족: {member.guild.name}에서 {member.display_name}에게 역할 배정 실패 "
                f"(Forbidden - 봇에게 역할 관리 권한이 없거나 역할이 봇보다 높음)"
            )
            
        except discord.HTTPException as e:
            logger.error(
                f"❌ HTTP 오류: {member.guild.name}에서 {member.display_name}에게 역할 배정 실패 "
                f"(HTTPException: {e})"
            )
            
        except ValueError as e:
            logger.error(
                f"❌ 잘못된 역할 ID: {member.guild.name}에서 역할 ID '{settings.get('role_id')}' "
                f"형식 오류 ({e})"
            )
            
        except Exception as e:
            logger.error(
                f"❌ 예상치 못한 오류: {member.guild.name}에서 {member.display_name}에게 "
                f"역할 배정 중 오류 발생 ({type(e).__name__}: {e})"
            )

    async def on_member_remove(self, member: discord.Member):
        """멤버가 서버를 떠날 때 로깅 (선택사항)"""
        
        # 봇은 제외
        if member.bot:
            return
        
        logger.info(f"👋 멤버 떠남: {member.display_name} (ID: {member.id}) from {member.guild.name}")

    async def on_guild_join(self, guild):
        """새 길드 참여 시"""
        logger.info(f"🆕 새 서버 참여: {guild.name}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """음성 채널 상태 변경 이벤트"""
        try:
            # 1. 기존 voice_level_tracker 처리
            if self.voice_level_tracker:
                if before.channel is None and after.channel is not None:
                    await self.voice_level_tracker.handle_voice_join(member, after.channel)
                elif before.channel is not None and after.channel is None:
                    await self.voice_level_tracker.handle_voice_leave(member, before.channel)
                elif before.channel != after.channel:
                    await self.voice_level_tracker.handle_voice_move(member, before.channel, after.channel)
                elif before.self_mute != after.self_mute:
                    await self.voice_level_tracker.handle_mute_change(
                        member, before.self_mute, after.self_mute
                    )
                elif before.self_stream != after.self_stream:
                    await self.voice_level_tracker.handle_screen_share_change(
                        member, before.self_stream, after.self_stream
                    )
            
            # 2. 팀정보 업데이트 처리 추가
            team_info_cog = self.get_cog('TeamInfoCommands')
            if team_info_cog and not member.bot:
                guild_id = str(member.guild.id)
                
                # 모니터링 활성화 확인
                if guild_id in team_info_cog.active_guilds:
                    # before 채널 업데이트
                    if before.channel:
                        await team_info_cog._schedule_update(before.channel, allow_resend=False)
                    
                    # after 채널 업데이트  
                    if after.channel:
                        await team_info_cog._schedule_update(after.channel, allow_resend=True)
            
        except Exception as e:
            logger.error(f"Error in on_voice_state_update: {e}", exc_info=True)

    async def close(self):
        """봇 종료 시 실행"""
        try:
            if self.bamboo_scheduler:
                await self.bamboo_scheduler.stop()
                logger.info("대나무숲 스케줄로 종료")

            if self.recruitment_scheduler:
                await self.recruitment_scheduler.stop()
                logger.info("내전 모집 스케줄러 종료")

            if self.scrim_scheduler:
                await self.scrim_scheduler.stop()
                logger.info("스크림 스케줄러 종료")

            if self.tier_change_scheduler:
                await self.tier_change_scheduler.stop()
                logger.info("티어 변동 감지 스케줄러 종료")

            if self.voice_level_tracker:
                self.voice_level_tracker.stop()
                logger.info("음성 레벨 트래커 종료")

        except Exception as e:
            logger.error(f"Error stopping bamboo scheduler: {e}")
        
        await super().close()
    
    async def on_command_error(self, ctx, error):
        logger.error(f'Error in command {ctx.command}: {error}')

    async def on_interaction(self, interaction: discord.Interaction):
        """
        모든 interaction을 가로채서 처리
        Persistent Views의 동적 custom_id 처리를 위함
        """
        try:
            # custom_id가 없으면 무시
            if not interaction.data or 'custom_id' not in interaction.data:
                return
            
            custom_id = interaction.data['custom_id']
            
            # 🔧 ConsultationReplyView 처리 (1:1 상담 답장/종료)
            if custom_id.startswith('consultation:'):
                from commands.inquiry_system import ConsultationReplyView
                
                # custom_id 파싱: consultation:action:guild_id:ticket:user_id:is_admin
                parts = custom_id.split(':', 2)
                if len(parts) >= 3:
                    _, action, data = parts
                    data_parts = data.split(':')
                    
                    if len(data_parts) == 4:
                        guild_id, ticket_number, target_user_id, is_admin_str = data_parts
                        is_admin = bool(int(is_admin_str))
                        
                        # View 생성 (데이터 복원)
                        view = ConsultationReplyView(
                            bot=self,
                            guild_id=guild_id,
                            ticket_number=ticket_number,
                            target_user_id=target_user_id,
                            is_admin=is_admin
                        )
                        
                        # 해당 액션의 콜백 직접 호출
                        if action == 'reply':
                            await view.reply_button_callback(interaction)
                            return
                        elif action == 'end':
                            await view.end_button_callback(interaction)
                            return
                        
                        logger.info(f"✅ 상담 버튼 처리: {action} - {ticket_number}")
            
            # TicketManagementView 처리 (관리팀 문의 버튼)
            elif custom_id in ['ticket:reply', 'ticket:complete', 'ticket:delete']:
                from commands.inquiry_system import TicketManagementView
                
                # 메시지에서 티켓 번호 추출
                if not interaction.message or not interaction.message.embeds:
                    logger.error("❌ 메시지 또는 embed 없음")
                    return
                
                embed = interaction.message.embeds[0]
                guild_id = str(interaction.guild_id)
                ticket_number = None
                
                # Footer에서 추출: "티켓: #0011"
                if embed.footer and embed.footer.text:
                    footer_text = embed.footer.text
                    logger.debug(f"🔍 Footer 텍스트: {footer_text}")
                    
                    if '#' in footer_text:
                        # "티켓: #0011" → "#0011" 추출
                        parts = footer_text.split('#')
                        if len(parts) > 1:
                            # "#0011 • 오늘" 같은 경우 처리
                            ticket_part = parts[1].split()[0].split('•')[0].strip()
                            ticket_number = f"#{ticket_part}"
                            logger.debug(f"✅ Footer에서 추출: {ticket_number}")
                
                # 2️Title에서 추출: "📋 문의 답변 - #0011"
                if not ticket_number and embed.title:
                    logger.debug(f"🔍 Title: {embed.title}")
                    if '#' in embed.title:
                        parts = embed.title.split('#')
                        if len(parts) > 1:
                            ticket_part = parts[1].split()[0].strip()
                            ticket_number = f"#{ticket_part}"
                            logger.debug(f"✅ Title에서 추출: {ticket_number}")
                
                # 3️Fields에서 추출
                if not ticket_number:
                    for field in embed.fields:
                        logger.debug(f"🔍 Field: {field.name} = {field.value}")
                        if '티켓' in field.name or 'ticket' in field.name.lower():
                            value = field.value.strip()
                            if '#' in value:
                                ticket_number = value.strip('`').strip()
                            else:
                                # "#" 없으면 추가
                                ticket_number = f"#{value.strip('`').strip()}"
                            logger.debug(f"✅ Field에서 추출: {ticket_number}")
                            break
                
                if not ticket_number:
                    logger.error("❌ 티켓 번호를 찾을 수 없음")
                    await interaction.response.send_message(
                        "❌ 티켓 번호를 찾을 수 없습니다.",
                        ephemeral=True
                    )
                    return
                
                logger.info(f"🎫 추출된 티켓 번호: {ticket_number}")
                
                # DB에서 티켓 정보 조회
                inquiry = await self.db_manager.get_inquiry_by_ticket(
                    guild_id,
                    ticket_number  # ✅ "#0015" 형태로 조회
                )
                
                if not inquiry:
                    logger.error(f"❌ 티켓을 찾을 수 없음: {ticket_number}")
                    await interaction.response.send_message(
                        "❌ 티켓 정보를 찾을 수 없습니다.",
                        ephemeral=True
                    )
                    return
                
                logger.info(f"✅ 티켓 조회 성공: {ticket_number}")
                
                # View 생성 (데이터 복원)
                view = TicketManagementView(
                    bot=self,
                    guild_id=guild_id,
                    ticket_number=ticket_number,
                    is_anonymous=inquiry.get('is_anonymous', False),
                    user_id=inquiry['user_id']
                )
                
                # 해당 버튼의 콜백 호출
                if custom_id == 'ticket:reply':
                    await view.reply_button(interaction, None)
                    return
                elif custom_id == 'ticket:complete':
                    await view.complete_button(interaction, None)
                    return
                elif custom_id == 'ticket:delete':
                    await view.delete_button(interaction, None)
                    return
                
                logger.info(f"✅ 티켓 버튼 처리 완료: {custom_id} - {ticket_number}")
            
        except Exception as e:
            logger.error(f"❌ on_interaction 처리 오류: {e}", exc_info=True)


async def main():
    bot = RallyUpBot()
    
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("DISCORD_BOT_TOKEN이 .env 파일에 설정되지 않았습니다!")
        return
    
    try:
        await bot.start(token)
    except discord.LoginFailure:
        logger.error("Invalid bot token - 봇 토큰이 올바르지 않습니다")
    except Exception as e:
        logger.error(f"Bot startup failed: {e}")
    finally:
        await bot.close()

if __name__ == '__main__':
    asyncio.run(main())