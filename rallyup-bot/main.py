import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
import os
from database.database import DatabaseManager
from scheduler.bamboo_scheduler import BambooForestScheduler
from scheduler.recruitment_scheduler import RecruitmentScheduler
from scheduler.wordle_scheduler import WordleScheduler
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

            # logger.info("🔄 배틀태그 마이그레이션 시작...")
            # migration_result = await self.db_manager.migrate_battle_tags_to_new_table()
            # logger.info(f"✅ 마이그레이션 결과: {migration_result}")

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

            if not self.wordle_scheduler:
                self.wordle_scheduler = WordleScheduler(self)
                await self.wordle_scheduler.start()
                logger.info("띵지워들 스케줄러 시작")

            # 티어 변동 스케줄러 시작
            if not self.tier_change_scheduler:
                from scheduler.tier_change_scheduler import TierChangeScheduler
                self.tier_change_scheduler = TierChangeScheduler(self)
                await self.tier_change_scheduler.start()
                logger.info("티어 변동 감지 스케줄러 시작")

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
            'commands.wordle_game',
            'commands.inter_guild_scrim',
            'commands.team_balancing',
            'commands.nickname_format_admin',
            'commands.battle_tag_commands',
            'commands.battle_tag_log_admin',
            'commands.team_info',
            'commands.voice_level_admin',
            'commands.voice_level_user'
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

        await self.restore_recruitment_views()

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
            # 음성 레벨 트래커가 없으면 무시
            if not self.voice_level_tracker:
                return
            
            # Case 1: 음성 채널 입장 (before: None, after: 채널)
            if before.channel is None and after.channel is not None:
                await self.voice_level_tracker.handle_voice_join(member, after.channel)
            
            # Case 2: 음성 채널 퇴장 (before: 채널, after: None)
            elif before.channel is not None and after.channel is None:
                await self.voice_level_tracker.handle_voice_leave(member, before.channel)
            
            # Case 3: 채널 이동 (before: 채널A, after: 채널B)
            elif before.channel != after.channel:
                await self.voice_level_tracker.handle_voice_move(member, before.channel, after.channel)
            
            # Case 4: 음소거 상태 변경
            elif before.self_mute != after.self_mute:
                await self.voice_level_tracker.handle_mute_change(
                    member, before.self_mute, after.self_mute
                )
        
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

            if self.wordle_scheduler:
                await self.wordle_scheduler.stop()
                logger.info("띵지워들 스케줄러 종료")

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