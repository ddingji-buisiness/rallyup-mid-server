import discord
from discord.ext import commands
import asyncio
import logging
from dotenv import load_dotenv
import os
from database.database import DatabaseManager

# 환경변수 로드
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RallyUpBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db_manager = DatabaseManager()
    
    async def setup_hook(self):
        """봇 시작시 실행되는 설정"""
        # 데이터베이스 초기화
        await self.db_manager.initialize()
        logger.info("Database initialized successfully")
        
        # 커맨드 로드
        await self.load_commands()
        
        # 슬래시 커맨드 동기화
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def load_commands(self):
        """커맨드 로드"""
        commands_to_load = [
            'commands.help',
            'commands.match_result',
            'commands.position',
            'commands.dev_commands',
            'commands.scrim_session'
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
    
    async def on_command_error(self, ctx, error):
        logger.error(f'Error in command {ctx.command}: {error}')

# 봇 실행
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