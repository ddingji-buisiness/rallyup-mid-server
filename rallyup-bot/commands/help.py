# commands/help.py
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
            color=0x0099ff
        )
        
        embed.add_field(
            name="📊 /내전결과 [음성채널명] [결과] [포지션]",
            value="**사용법:**\n"
                  "`/내전결과 A팀 승리 탱딜딜힐힐`\n"
                  "`/내전결과 B팀 패배 딜탱딜힐힐`\n\n"
                  "**주의사항:**\n"
                  "• 해당 음성채널에 5명이 있어야 함\n"
                  "• 포지션: 탱커 1명, 힐러 1명 이상 필요\n"
                  "• 각 팀별로 개별 기록",
            inline=False
        )
        
        embed.add_field(
            name="🔧 포지션 표기법",
            value="**탱:** 탱커 (라인하르트, 윈스턴 등)\n"
                  "**딜:** 딜러 (겐지, 트레이서, 위도우 등)\n"
                  "**힐:** 힐러 (메르시, 아나, 루시우 등)",
            inline=False
        )
        
        embed.add_field(
            name="📈 개발 예정 기능",
            value="• `/내전정보` - 개인 통계 조회\n"
                  "• `/팀배정` - 자동 팀 배정\n"
                  "• `/승점비교` - 사용자 비교",
            inline=False
        )
        
        embed.set_footer(text="RallyUp Bot v1.0 | 각 팀별 개별 기록")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))