import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
import os
from database.database import DatabaseManager
from scheduler.bamboo_scheduler import BambooForestScheduler
from scheduler.recruitment_scheduler import RecruitmentScheduler

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

    async def setup_hook(self):
        """봇 시작시 실행되는 설정"""
        try:
            await self.db_manager.initialize()
            logger.info("Database initialized successfully")

            await self.load_commands()
            
            await self.bamboo_scheduler.start()
            logger.info("🎋 Bamboo forest scheduler started")

            if not self.recruitment_scheduler:
                self.recruitment_scheduler = RecruitmentScheduler(self)
                await self.recruitment_scheduler.start()
                logger.info("내전 모집 스케줄러 시작")

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
            'commands.position',
            'commands.dev_commands',
            'commands.scrim_session',
            'commands.clan_scrim',
            'commands.user_application',
            'commands.admin_system',
            'commands.bamboo_forest',
            'commands.scrim_recruitment'
        ]
        
        for command_module in commands_to_load:
            try:
                await self.load_extension(command_module)
                logger.info(f"✅ Loaded: {command_module}")
            except Exception as e:
                logger.error(f"❌ Failed to load {command_module}: {e}")
        
        logger.info("Command loading completed")
    
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # 봇 상태 설정
        await self.change_presence(
            activity=discord.Game(name="RallyUp 클랜 관리 | /help")
        )
        
        # 스케줄러 상태 확인
        if self.bamboo_scheduler.running:
            logger.info("🎋 Bamboo forest scheduler is running")
        else:
            logger.warning("🎋 Bamboo forest scheduler is not running!")

        if self.recruitment_scheduler and self.recruitment_scheduler.is_running:
            logger.info("🕐 내전 모집 스케줄러가 실행 중입니다")
        else:
            logger.warning("🕐 내전 모집 스케줄러가 실행되지 않았습니다!")

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

    async def close(self):
        """봇 종료 시 실행"""
        try:
            if self.bamboo_scheduler:
                await self.bamboo_scheduler.stop()
                logger.info("대나무숲 스케줄로 종료")

            if self.recruitment_scheduler:
                await self.recruitment_scheduler.stop()
                logger.info("내전 모집 스케줄러 종료")

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