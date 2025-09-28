"""
팀 밸런싱 명령어 구현
자동으로 균형잡힌 5vs5 팀을 생성하는 기능
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
import asyncio
import logging

from utils.balance_ui import PlayerSelectionView
from utils.balance_algorithm import TeamBalancer, BalancingMode

# 로깅 설정
logger = logging.getLogger(__name__)

class TeamBalancingCommand(commands.Cog):
    """팀 밸런싱 명령어 Cog"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}  # 길드별 활성 세션 추적
    
    async def is_admin_or_elevated_user(self, interaction: discord.Interaction) -> bool:
        """
        관리자 또는 권한이 있는 사용자인지 확인
        - 서버 관리자
        - 봇 관리자
        - 특정 역할 보유자 (선택적으로 구현 가능)
        """
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 서버 소유자는 항상 허용
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        # Discord 서버 관리 권한 확인
        if interaction.user.guild_permissions.manage_guild:
            return True
        
        # 봇 관리자 권한 확인
        try:
            is_bot_admin = await self.bot.db_manager.is_server_admin(guild_id, user_id)
            if is_bot_admin:
                return True
        except Exception as e:
            logger.warning(f"관리자 권한 확인 중 오류: {e}")
        
        # TODO: 추가적인 권한 확인 로직 (예: 특정 역할)
        # 예를 들어, "내전 관리자" 역할을 가진 사용자에게 권한 부여
        # balancing_role = discord.utils.get(interaction.guild.roles, name="내전 관리자")
        # if balancing_role and balancing_role in interaction.user.roles:
        #     return True
        
        return False
    
    @app_commands.command(name="팀밸런싱", description="자동으로 균형잡힌 5vs5 팀을 생성합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def team_balancing(self, interaction: discord.Interaction):
        """
        메인 팀 밸런싱 명령어
        관리자만 사용 가능
        """
        # 권한 체크
        if not await self.is_admin_or_elevated_user(interaction):
            embed = discord.Embed(
                title="❌ 권한 부족",
                description="이 명령어는 관리자만 사용할 수 있습니다.",
                color=0xff4444
            )
            embed.add_field(
                name="💡 권한이 필요한 이유",
                value="팀 밸런싱은 게임의 공정성에 영향을 미치므로 관리자만 사용할 수 있습니다.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        guild_id = str(interaction.guild_id)
        
        # 이미 진행 중인 세션이 있는지 확인
        if guild_id in self.active_sessions:
            embed = discord.Embed(
                title="⚠️ 이미 진행 중인 세션",
                description="현재 다른 팀 밸런싱 세션이 진행 중입니다.",
                color=0xffaa00
            )
            embed.add_field(
                name="💡 해결 방법",
                value="• 기존 세션이 완료될 때까지 대기하거나\n• 기존 세션을 취소한 후 다시 시도해주세요.",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # 밸런싱 가능한 유저 목록 조회
            eligible_players = await self.bot.db_manager.get_eligible_users_for_balancing(
                guild_id, min_games=3
            )
            
            if len(eligible_players) < 10:
                embed = discord.Embed(
                    title="❌ 참가 가능한 플레이어 부족",
                    description=f"팀 밸런싱을 위해서는 최소 10명의 플레이어가 필요합니다.",
                    color=0xff4444
                )
                embed.add_field(
                    name="📊 현재 상황",
                    value=f"• 조건을 만족하는 플레이어: **{len(eligible_players)}명**\n"
                          f"• 필요한 플레이어: **10명**\n"
                          f"• 부족한 플레이어: **{10 - len(eligible_players)}명**",
                    inline=False
                )
                embed.add_field(
                    name="✅ 참가 조건",
                    value="• 서버에 등록된 유저\n• 최소 3경기 이상 참여\n• 승인된 상태",
                    inline=False
                )
                embed.add_field(
                    name="💡 해결 방법",
                    value="• 더 많은 플레이어가 내전에 참여하도록 유도\n• 신규 플레이어 등록 촉진\n• 최소 게임 수 조건 충족까지 대기",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed)
                return
            
            # 세션 등록
            self.active_sessions[guild_id] = {
                'user_id': str(interaction.user.id),
                'started_at': discord.utils.utcnow()
            }
            
            # 서버 포지션 분포 정보 조회 (참고용)
            position_distribution = await self.bot.db_manager.get_server_position_distribution(guild_id)
            
            # 플레이어 선택 View 시작
            selection_view = PlayerSelectionView(self.bot, guild_id, eligible_players)
            selection_view.interaction_user = interaction.user
            
            embed = discord.Embed(
                title="🎯 팀 밸런싱",
                description="균형잡힌 5vs5 팀을 자동으로 생성합니다.\n먼저 참가할 10명의 플레이어를 선택해주세요.",
                color=0x0099ff
            )
            
            embed.add_field(
                name="📊 선택 가능한 플레이어",
                value=f"총 **{len(eligible_players)}명** (최소 3경기 이상)",
                inline=True
            )
            
            # 포지션 분포 정보 추가
            if position_distribution and position_distribution['distribution']:
                dist_text = ""
                for position, data in position_distribution['distribution'].items():
                    if position != '미설정':
                        emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚"
                        dist_text += f"{emoji} {position}: {data['count']}명 ({data['percentage']:.1f}%)\n"
                
                if dist_text:
                    embed.add_field(
                        name="🎮 서버 포지션 분포",
                        value=dist_text.strip(),
                        inline=True
                    )
            
            embed.add_field(
                name="💡 사용 방법",
                value="1️⃣ 드롭다운에서 참가자 10명 선택\n"
                      "2️⃣ 밸런싱 모드 선택\n"
                      "3️⃣ 자동 계산된 최적 팀 구성 확인\n"
                      "4️⃣ 팀 구성 확정",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 밸런싱 기준",
                value="• 포지션별 승률 및 숙련도\n• 팀 간 스킬 균형\n• 포지션 적합도\n• 과거 팀워크 데이터",
                inline=False
            )
            
            embed.set_footer(
                text=f"요청자: {interaction.user.display_name} | 5분 후 자동 만료",
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.followup.send(embed=embed, view=selection_view)
            
            # 세션 타임아웃 관리
            await self.manage_session_timeout(guild_id, selection_view)
            
        except Exception as e:
            logger.error(f"팀 밸런싱 명령어 실행 중 오류: {e}", exc_info=True)
            
            # 세션 정리
            if guild_id in self.active_sessions:
                del self.active_sessions[guild_id]
            
            embed = discord.Embed(
                title="❌ 오류 발생",
                description="팀 밸런싱을 시작하는 중 오류가 발생했습니다.",
                color=0xff4444
            )
            embed.add_field(
                name="🔍 오류 정보",
                value=f"```{str(e)[:1000]}```",
                inline=False
            )
            embed.add_field(
                name="💡 해결 방법",
                value="• 잠시 후 다시 시도해보세요\n• 지속적으로 발생하면 관리자에게 문의하세요",
                inline=False
            )
            
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                # followup이 실패한 경우 edit으로 시도
                try:
                    await interaction.edit_original_response(embed=embed, view=None)
                except:
                    pass  # 모든 응답 방법이 실패한 경우 무시
    
    async def manage_session_timeout(self, guild_id: str, view: discord.ui.View):
        """세션 타임아웃 관리"""
        try:
            # View의 타임아웃을 기다림
            await view.wait()
        except:
            pass
        finally:
            # 세션 정리
            if guild_id in self.active_sessions:
                del self.active_sessions[guild_id]
    
    @app_commands.command(name="밸런싱상태", description="현재 진행 중인 팀 밸런싱 세션 상태를 확인합니다")
    async def balancing_status(self, interaction: discord.Interaction):
        """현재 밸런싱 세션 상태 확인"""
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.active_sessions:
            embed = discord.Embed(
                title="💤 진행 중인 세션 없음",
                description="현재 진행 중인 팀 밸런싱 세션이 없습니다.",
                color=0x888888
            )
            embed.add_field(
                name="💡 새 세션 시작",
                value="`/팀밸런싱` 명령어로 새로운 세션을 시작할 수 있습니다.",
                inline=False
            )
        else:
            session_info = self.active_sessions[guild_id]
            started_by = await self.bot.fetch_user(int(session_info['user_id']))
            
            embed = discord.Embed(
                title="⏳ 진행 중인 세션",
                description="현재 팀 밸런싱 세션이 진행 중입니다.",
                color=0x0099ff
            )
            embed.add_field(
                name="👤 시작한 사용자",
                value=started_by.mention if started_by else "알 수 없음",
                inline=True
            )
            embed.add_field(
                name="🕐 시작 시간",
                value=f"<t:{int(session_info['started_at'].timestamp())}:R>",
                inline=True
            )
            embed.add_field(
                name="ℹ️ 상태",
                value="참가자 선택 또는 밸런싱 진행 중",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="밸런싱취소", description="진행 중인 팀 밸런싱 세션을 강제 취소합니다 (관리자 전용)")
    @app_commands.default_permissions(manage_guild=True)
    async def cancel_balancing(self, interaction: discord.Interaction):
        """진행 중인 밸런싱 세션 강제 취소"""
        if not await self.is_admin_or_elevated_user(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild_id)
        
        if guild_id not in self.active_sessions:
            embed = discord.Embed(
                title="💤 취소할 세션 없음",
                description="현재 진행 중인 팀 밸런싱 세션이 없습니다.",
                color=0x888888
            )
        else:
            # 세션 정리
            del self.active_sessions[guild_id]
            
            embed = discord.Embed(
                title="✅ 세션 취소 완료",
                description="진행 중이던 팀 밸런싱 세션이 취소되었습니다.",
                color=0x00ff00
            )
            embed.add_field(
                name="💡 새 세션",
                value="`/팀밸런싱` 명령어로 새로운 세션을 시작할 수 있습니다.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="밸런싱도움말", description="팀 밸런싱 기능 사용법을 안내합니다")
    async def balancing_help(self, interaction: discord.Interaction):
        """팀 밸런싱 도움말"""
        embed = discord.Embed(
            title="🎯 팀 밸런싱 가이드",
            description="RallyUp Bot의 AI 기반 팀 밸런싱 시스템을 소개합니다.",
            color=0x0099ff
        )
        
        embed.add_field(
            name="🎮 기본 사용법",
            value="1. `/팀밸런싱` - 밸런싱 시작\n"
                  "2. 참가자 10명 선택\n"
                  "3. 밸런싱 모드 선택\n"
                  "4. 결과 확인 및 확정",
            inline=False
        )
        
        embed.add_field(
            name="⚙️ 밸런싱 모드",
            value="⚡ **빠른**: 기본 승률 기반 (~1초)\n"
                  "🎯 **정밀**: 모든 요소 고려 (~5초)\n"
                  "🔬 **실험적**: 새로운 조합 시도 (~2초)",
            inline=False
        )
        
        embed.add_field(
            name="📊 밸런싱 기준",
            value="• **포지션별 숙련도**: 탱/딜/힐 각각의 승률\n"
                  "• **경험치 보정**: 게임 수에 따른 신뢰도\n"
                  "• **팀 밸런스**: 양팀 스킬 차이 최소화\n"
                  "• **포지션 적합도**: 주포지션 일치도",
            inline=False
        )
        
        embed.add_field(
            name="✅ 참가 조건",
            value="• 서버에 등록된 유저 (`/유저신청`)\n"
                  "• 최소 3경기 이상 참여\n"
                  "• 승인 상태",
            inline=True
        )
        
        embed.add_field(
            name="🔧 관리 명령어",
            value="• `/밸런싱상태` - 세션 상태 확인\n"
                  "• `/밸런싱취소` - 세션 강제 취소\n"
                  "• `/밸런싱도움말` - 이 도움말",
            inline=True
        )
        
        embed.add_field(
            name="💡 팁",
            value="• 다양한 포지션의 플레이어를 포함시키면 더 좋은 결과\n"
                  "• 정밀 모드 추천 (가장 균형잡힌 결과)\n"
                  "• 여러 조합을 비교해보고 최적의 팀 선택",
            inline=False
        )
        
        embed.set_footer(
            text="🤖 RallyUp Bot AI Team Balancing System",
            icon_url=self.bot.user.display_avatar.url if self.bot.user else None
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def cog_load(self):
        """Cog 로드 시 실행"""
        logger.info("TeamBalancingCommand Cog이 로드되었습니다.")
    
    async def cog_unload(self):
        """Cog 언로드 시 실행"""
        # 모든 활성 세션 정리
        self.active_sessions.clear()
        logger.info("TeamBalancingCommand Cog이 언로드되었습니다.")

async def setup(bot):
    """Cog 설정 함수"""
    await bot.add_cog(TeamBalancingCommand(bot))