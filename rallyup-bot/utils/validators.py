import discord
from discord.ext import commands
from discord import app_commands

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="RallyUp 봇 사용법을 확인합니다")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎮 RallyUp Bot 사용법",
            description="오버워치 클랜 내전 관리를 위한 봇입니다",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📊 /내전결과",
            value="`/내전결과 [팀번호] [결과] [포지션]`\n"
                  "예시: `/내전결과 1팀 승리 탱딜딜힐힐`",
            inline=False
        )
        
        embed.add_field(
            name="⚖️ /팀배정",
            value="`/팀배정 [조건]`\n"
                  "조건: `랜덤`, `승률`, `승점`",
            inline=False
        )
        
        embed.add_field(
            name="📈 /내전정보",
            value="나의 승률과 승점 정보를 확인합니다",
            inline=False
        )
        
        embed.add_field(
            name="🆚 /승점비교",
            value="`/승점비교 [@사용자1] [@사용자2]`\n"
                  "두 사용자의 승점을 비교합니다",
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot v1.0 | MVP")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))