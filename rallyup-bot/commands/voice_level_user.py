"""
음성 레벨 시스템 - 유저 커맨드
Phase 2: 레벨, EXP, 통계 조회
"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from utils.voice_exp_calculator import VoiceExpCalculator

logger = logging.getLogger(__name__)


class VoiceLevelUser(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db_manager
        self.exp_calculator = VoiceExpCalculator(self.db)
    
    @app_commands.command(name="내레벨", description="내 레벨과 통계를 확인합니다")
    async def my_level(self, interaction: discord.Interaction):
        """내 레벨 및 통계 조회"""
        try:
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                await interaction.response.send_message(
                    "❌ 이 서버에서는 음성 레벨 시스템이 활성화되지 않았습니다.",
                    ephemeral=True
                )
                return
            
            # 레벨 정보 조회
            user_level = await self.db.get_user_level(guild_id, user_id)
            
            if not user_level:
                await interaction.response.send_message(
                    "ℹ️ 아직 음성 채널에서 활동 기록이 없습니다.\n"
                    "음성 채널에서 다른 유저들과 함께 시간을 보내면 레벨을 획득할 수 있습니다!",
                    ephemeral=True
                )
                return
            
            # 현재 온라인 유저 ID 수집
            online_user_ids = []
            for voice_channel in interaction.guild.voice_channels:
                for member in voice_channel.members:
                    if not member.bot:
                        online_user_ids.append(str(member.id))
            
            # 순위 조회
            rank_info = await self.db.get_user_rank(guild_id, user_id)
            
            # 관계 정보 조회
            relationships = await self.db.get_user_relationships(guild_id, user_id)
            
            # 함께 안 한 멤버 조회
            never_played = await self.db.get_members_never_played_with_priority(
                guild_id, user_id, online_user_ids, limit=3
            )
            
            # 오래 안 논 친구 조회
            dormant_friends = await self.db.get_dormant_relationships(
                guild_id, user_id, min_hours=1.0, days_threshold=7, limit=3
            )
            
            # Embed 생성
            embed = discord.Embed(
                title=f"📊 {interaction.user.display_name}님의 통계",
                color=discord.Color.blue()
            )
            
            # 레벨 & EXP
            current_level = user_level['current_level']
            current_exp = user_level['current_exp']
            required_exp = self.exp_calculator.get_required_exp(current_level + 1)
            progress_percentage = (current_exp / required_exp * 100) if required_exp > 0 else 0
            
            # 진행 바 생성
            bar_length = 20
            filled = int(bar_length * current_exp / required_exp) if required_exp > 0 else 0
            bar = "█" * filled + "░" * (bar_length - filled)
            
            embed.add_field(
                name="🎯 레벨 & EXP",
                value=(
                    f"**레벨 {current_level}**\n"
                    f"{bar} {progress_percentage:.1f}%\n"
                    f"`{current_exp:,} / {required_exp:,} exp`\n"
                    f"총 누적: `{user_level['total_exp']:,} exp`"
                ),
                inline=False
            )
            
            # 순위 정보
            embed.add_field(
                name="🏆 서버 순위",
                value=(
                    f"레벨 순위: **#{rank_info['level_rank']}** / {rank_info['total_users']}명\n"
                    f"다양성 순위: **#{rank_info['diversity_rank']}** / {rank_info['total_users']}명"
                ),
                inline=False
            )
            
            # 플레이 시간
            total_seconds = user_level['total_play_time_seconds']
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            
            embed.add_field(
                name="⏱️ 플레이 시간",
                value=f"총 **{hours}시간 {minutes}분**",
                inline=True
            )

            # 화면 공유 시간 표시
            screen_share_seconds = user_level.get('total_screen_share_seconds', 0)
            if screen_share_seconds > 0:
                ss_hours = screen_share_seconds // 3600
                ss_minutes = (screen_share_seconds % 3600) // 60
                ss_percentage = min(100, (screen_share_seconds / max(total_seconds, 1)) * 100)
                
                embed.add_field(
                    name="🖥️ 화면 공유",
                    value=f"**{ss_hours}h {ss_minutes}m** ({ss_percentage:.0f}%)",
                    inline=True
                )

            # 함께 플레이한 사람
            unique_partners = user_level['unique_partners_count']
            total_members = rank_info['total_users']

            if unique_partners > total_members:
                display_text = f"**{unique_partners}명** (역대 {total_members}명)"
            else:
                display_text = f"**{unique_partners}명** / {total_members}명"
            
            embed.add_field(
                name="🤝 함께 플레이한 사람",
                value=display_text,
                inline=True
            )
            
            # 일일 진행도
            daily_gained = user_level['daily_exp_gained']
            daily_limit = settings.get('daily_exp_limit', 5000)
            daily_percentage = (daily_gained / daily_limit * 100) if daily_limit > 0 else 0
            
            embed.add_field(
                name="📅 오늘의 EXP",
                value=f"`{daily_gained:,} / {daily_limit:,}` ({daily_percentage:.0f}%)",
                inline=False
            )
            
            # 단짝 TOP 3
            if relationships:
                top_3 = sorted(relationships, key=lambda x: x['total_time_seconds'], reverse=True)[:3]
                partner_list = []
                
                for idx, rel in enumerate(top_3, start=1):
                    partner_member = interaction.guild.get_member(int(rel['partner_id']))
                    partner_name = partner_member.display_name if partner_member else f"User {rel['partner_id']}"
                    
                    rel_seconds = rel['total_time_seconds']
                    rel_hours = rel_seconds // 3600
                    rel_minutes = (rel_seconds % 3600) // 60
                    
                    # 이모지 추가
                    emoji = "💎" if idx == 1 else "🔥" if idx == 2 else "⭐"
                    partner_list.append(f"{emoji} **{partner_name}**: {rel_hours}h {rel_minutes}m")
                
                embed.add_field(
                    name="👥 단짝 TOP 3",
                    value="\n".join(partner_list) if partner_list else "아직 없음",
                    inline=False
                )
            
            # 새로운 인연
            if never_played:
                never_played_list = []
                for entry in never_played:
                    member = interaction.guild.get_member(int(entry['user_id']))
                    if member:
                        # 온라인이면 🟢, 오프라인이면 이모지 없음
                        status = "🟢 " if entry['is_online'] else ""
                        never_played_list.append(f"{status}**{member.display_name}**")
                
                if never_played_list:
                    embed.add_field(
                        name="🌱 새로운 인연 (함께 안 한 멤버)",
                        value="• " + "\n• ".join(never_played_list),
                        inline=False
                    )
            
            # 오래 안 논 친구
            if dormant_friends:
                dormant_list = []
                for friend in dormant_friends:
                    member = interaction.guild.get_member(int(friend['partner_id']))
                    if member:
                        total_h = int(friend['total_hours'])
                        days = friend['days_ago']
                        dormant_list.append(
                            f"• **{member.display_name}**: "
                            f"마지막 {days}일 전 (총 {total_h}h)"
                        )
                
                if dormant_list:
                    embed.add_field(
                        name="🕐 오랜만이에요",
                        value="\n".join(dormant_list),
                        inline=False
                    )
            
            # 동적 유도 메시지
            diversity_ratio = unique_partners / max(total_members - 1, 1)
            
            if diversity_ratio < 0.3:
                tip = "💡 **다양한 멤버와 놀면 레벨업이 빨라져요!**"
            elif diversity_ratio < 0.6:
                tip = "🎉 **이미 절반 이상의 멤버와 놀았어요!**"
            elif diversity_ratio < 0.9:
                tip = "🌟 **거의 다 왔어요! 조금만 더 다양하게 놀아보세요!**"
            else:
                tip = "👑 **거의 모든 멤버와 함께 플레이했네요!**"
            
            # 온라인 멤버가 있으면 추가 메시지
            online_never = [e for e in never_played if e['is_online']]
            if online_never:
                tip += f"\n🟢 지금 음성 채널에 새로운 멤버가 있어요!"
            
            embed.add_field(
                name="💬 TIP",
                value=tip,
                inline=False
            )
            
            embed.set_footer(text=f"서버 ID: {guild_id} | 🟢 = 현재 온라인")
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in my_level: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="관계", description="특정 유저와의 관계 정보를 확인합니다")
    @app_commands.describe(유저="확인할 유저")
    async def check_relationship_detailed(
        self,
        interaction: discord.Interaction,
        유저: discord.Member
    ):
        """두 유저 간 관계 정보 상세 조회"""
        try:
            guild_id = str(interaction.guild.id)
            user_id = str(interaction.user.id)
            partner_id = str(유저.id)
            
            if user_id == partner_id:
                await interaction.response.send_message(
                    "❌ 자기 자신과의 관계는 확인할 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                await interaction.response.send_message(
                    "❌ 이 서버에서는 음성 레벨 시스템이 활성화되지 않았습니다.",
                    ephemeral=True
                )
                return
            
            # 관계 조회
            relationship = await self.db.get_relationship(guild_id, user_id, partner_id)
            
            if not relationship:
                await interaction.response.send_message(
                    f"ℹ️ {유저.mention}님과 아직 함께 음성 채널에서 시간을 보낸 기록이 없습니다.",
                    ephemeral=True
                )
                return
            
            total_seconds = relationship['total_time_seconds']
            total_hours = total_seconds / 3600.0
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            # 관계 배율 계산
            multiplier = self.exp_calculator.calculate_decay_multiplier(total_hours)
            multiplier_percentage = multiplier * 100
            
            embed = discord.Embed(
                title="🤝 관계 정보",
                description=f"{interaction.user.mention} ↔ {유저.mention}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="⏱️ 함께한 시간",
                value=f"**{hours}시간 {minutes}분 {seconds}초**",
                inline=False
            )
            
            embed.add_field(
                name="💎 현재 EXP 배율",
                value=f"**{multiplier_percentage:.0f}%**",
                inline=True
            )
            
            # 배율 상태 설명
            if multiplier >= 1.10:
                status = "✨ 새로운 인연! (높은 EXP)"
            elif multiplier >= 0.80:
                status = "🔥 좋은 관계 (보통 EXP)"
            elif multiplier >= 0.50:
                status = "👥 친한 친구 (중간 EXP)"
            elif multiplier >= 0.35:
                status = "💫 단짝 (낮은 EXP)"
            else:
                status = "👑 전설의 듀오 (최소 EXP)"
            
            embed.add_field(
                name="📊 관계 등급",
                value=status,
                inline=True
            )
            
            if relationship['last_played_together']:
                from datetime import datetime
                last_played = datetime.fromisoformat(relationship['last_played_together'])
                timestamp = int(last_played.timestamp())
                
                embed.add_field(
                    name="📅 마지막 플레이",
                    value=f"<t:{timestamp}:R>",
                    inline=False
                )
            
            # 마일스톤 표시
            milestones = [1, 5, 10, 20, 50, 100, 200, 500]
            next_milestone = None
            
            for milestone in milestones:
                if hours < milestone:
                    next_milestone = milestone
                    break
            
            if next_milestone:
                remaining_hours = next_milestone - hours
                embed.add_field(
                    name="🎯 다음 마일스톤",
                    value=f"{next_milestone}시간까지 **{remaining_hours}시간** 남음",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏆 마일스톤",
                    value="모든 마일스톤 달성! 🎉",
                    inline=False
                )
            
            embed.set_footer(text="Phase 2: EXP 계산 활성화")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in check_relationship_detailed: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="레벨순위", description="서버 레벨 순위를 확인합니다")
    @app_commands.describe(페이지="확인할 페이지 (1-10)")
    async def level_leaderboard(
        self,
        interaction: discord.Interaction,
        페이지: Optional[int] = 1
    ):
        """레벨 순위표"""
        try:
            guild_id = str(interaction.guild.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                await interaction.response.send_message(
                    "❌ 이 서버에서는 음성 레벨 시스템이 활성화되지 않았습니다.",
                    ephemeral=True
                )
                return
            
            # 페이지 유효성 검사
            페이지 = max(1, min(10, 페이지))
            
            # 순위 조회
            leaderboard = await self.db.get_level_leaderboard(guild_id, limit=10)
            
            if not leaderboard:
                await interaction.response.send_message(
                    "ℹ️ 아직 레벨 데이터가 없습니다.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🏆 레벨 순위 (Top 10)",
                description="서버에서 가장 높은 레벨을 보유한 유저들",
                color=discord.Color.gold()
            )
            
            rank_emojis = ["🥇", "🥈", "🥉"]
            
            for idx, entry in enumerate(leaderboard, start=1):
                member = interaction.guild.get_member(int(entry['user_id']))
                member_name = member.display_name if member else f"User {entry['user_id']}"
                
                emoji = rank_emojis[idx - 1] if idx <= 3 else f"**{idx}.**"
                
                hours = entry['total_play_time_seconds'] // 3600
                
                embed.add_field(
                    name=f"{emoji} {member_name}",
                    value=(
                        f"레벨 **{entry['current_level']}** | "
                        f"{entry['total_exp']:,} exp\n"
                        f"플레이: {hours}시간 | "
                        f"파트너: {entry['unique_partners_count']}명"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"페이지 {페이지}/1 | 서버: {interaction.guild.name}")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in level_leaderboard: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="다양성순위", description="다양한 사람들과 플레이한 순위를 확인합니다")
    async def diversity_leaderboard(self, interaction: discord.Interaction):
        """다양성 순위표 (많은 사람과 플레이한 순)"""
        try:
            guild_id = str(interaction.guild.id)
            
            # 설정 확인
            settings = await self.db.get_voice_level_settings(guild_id)
            if not settings['enabled']:
                await interaction.response.send_message(
                    "❌ 이 서버에서는 음성 레벨 시스템이 활성화되지 않았습니다.",
                    ephemeral=True
                )
                return
            
            # 순위 조회
            leaderboard = await self.db.get_diversity_leaderboard(guild_id, limit=10)
            
            if not leaderboard:
                await interaction.response.send_message(
                    "ℹ️ 아직 데이터가 없습니다.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🌟 다양성 순위 (Top 10)",
                description="가장 다양한 사람들과 함께 플레이한 유저들",
                color=discord.Color.purple()
            )
            
            rank_emojis = ["🥇", "🥈", "🥉"]
            
            for idx, entry in enumerate(leaderboard, start=1):
                member = interaction.guild.get_member(int(entry['user_id']))
                member_name = member.display_name if member else f"User {entry['user_id']}"
                
                emoji = rank_emojis[idx - 1] if idx <= 3 else f"**{idx}.**"
                
                embed.add_field(
                    name=f"{emoji} {member_name}",
                    value=(
                        f"함께 플레이: **{entry['unique_partners_count']}명**\n"
                        f"레벨 {entry['current_level']} | {entry['total_exp']:,} exp"
                    ),
                    inline=False
                )
            
            embed.set_footer(text=f"서버: {interaction.guild.name}")
            
            await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in diversity_leaderboard: {e}", exc_info=True)
            await interaction.response.send_message(
                f"❌ 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(VoiceLevelUser(bot))
    logger.info("✅ VoiceLevelUser cog loaded")