import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List
from datetime import datetime
import re

class SimpleUserManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="정보수정", description="내 현재 시즌 티어를 업데이트합니다")
    @app_commands.describe(
        현시즌티어="현재 시즌 티어 (예: 플레3, 다이아1, 골드2)",
        메인포지션="메인 포지션 변경 (선택사항)",
        배틀태그="배틀태그 변경 (선택사항)"
    )
    @app_commands.choices(메인포지션=[
        app_commands.Choice(name="탱커", value="탱커"),
        app_commands.Choice(name="딜러", value="딜러"),
        app_commands.Choice(name="힐러", value="힐러")
    ])
    async def update_info(
        self,
        interaction: discord.Interaction,
        현시즌티어: str,
        메인포지션: app_commands.Choice[str] = None,
        배틀태그: str = None
    ):
        user_id = str(interaction.user.id)
        
        try:
            # 기존 유저 정보 확인
            guild_id = str(interaction.guild_id)
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, user_id)
            if not user_data:
                await interaction.response.send_message(
                    "❌ 먼저 `/유저신청` 명령어로 등록해주세요!",
                    ephemeral=True
                )
                return
            
            # 업데이트할 데이터 준비
            update_data = {"current_season_tier": 현시즌티어}
            
            if 메인포지션:
                update_data["main_position"] = 메인포지션.value
            
            if 배틀태그:
                if not self._validate_battle_tag(배틀태그):
                    await interaction.response.send_message(
                        "❌ 올바른 배틀태그 형식이 아닙니다. (예: TestUser#1234)",
                        ephemeral=True
                    )
                    return
                
                # 중복 체크
                existing = await self.bot.db_manager.check_battle_tag_exists(배틀태그, exclude_user_id=user_id)
                if existing:
                    await interaction.response.send_message(
                        f"❌ 배틀태그 `{배틀태그}`는 이미 다른 유저가 사용 중입니다.",
                        ephemeral=True
                    )
                    return
                update_data["battle_tag"] = 배틀태그
            
            # 정보 업데이트
            success = await self.bot.db_manager.update_user_application(user_id, update_data)
            
            if not success:
                await interaction.response.send_message(
                    "❌ 정보 업데이트 중 오류가 발생했습니다.",
                    ephemeral=True
                )
                return
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 정보 업데이트 완료!",
                color=0x00ff88
            )
            
            changes = []
            changes.append(f"🎯 **현재 티어:** {현시즌티어}")
            if 메인포지션:
                changes.append(f"🎮 **메인 포지션:** {메인포지션.value}")
            if 배틀태그:
                changes.append(f"🏷️ **배틀태그:** {배틀태그}")
            
            embed.add_field(
                name="📝 변경된 정보",
                value="\n".join(changes),
                inline=False
            )
            
            # 내전 통계 미리보기
            stats = await self.bot.db_manager.get_detailed_user_stats(user_id, str(interaction.guild_id))
            if stats and stats['total_games'] > 0:
                embed.add_field(
                    name="📊 내전 통계",
                    value=f"총 **{stats['total_games']}경기** | "
                          f"승률 **{stats['overall_winrate']:.1f}%** | "
                          f"({stats['wins']}승 {stats['losses']}패)",
                    inline=False
                )
            
            embed.set_footer(text="내전 참여 시 자동으로 세부 통계가 업데이트됩니다!")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 정보 업데이트 중 오류: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="내정보", description="내 종합 정보와 통계를 확인합니다")
    async def my_info(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        try:
            # 기본 정보
            guild_id = str(interaction.guild_id)
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, user_id)
            if not user_data:
                await interaction.response.send_message(
                    "❌ 등록된 정보가 없습니다. `/유저신청` 명령어로 먼저 등록해주세요!",
                    ephemeral=True
                )
                return
            
            # 내전 통계
            match_stats = await self.bot.db_manager.get_detailed_user_stats(user_id, guild_id)
            
            embed = discord.Embed(
                title=f"👤 {interaction.user.display_name}님의 정보",
                color=interaction.user.color
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 기본 정보
            registered_at = user_data.get('registered_at')
            if isinstance(registered_at, str):
                try:
                    registered_at = datetime.fromisoformat(registered_at)
                except:
                    registered_at = datetime.now()
            elif registered_at is None:
                registered_at = datetime.now()
            
            basic_info = (
                f"🏷️ **배틀태그:** {user_data.get('battle_tag', 'N/A')}\n"
                f"🎮 **메인 포지션:** {user_data.get('main_position', 'N/A')}\n"  
                f"🎯 **현재 티어:** {user_data.get('current_season_tier', 'N/A')}\n"
                f"📅 **등록일:** <t:{int(registered_at.timestamp())}:R>"
            )
            embed.add_field(
                name="📋 기본 정보",
                value=basic_info,
                inline=False
            )
            
            # 내전 통계 (자동 수집된 데이터)
            if match_stats and match_stats['total_games'] > 0:
                stats_info = (
                    f"🎮 **총 경기:** {match_stats['total_games']}경기\n"
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}% ({match_stats['wins']}승 {match_stats['losses']}패)\n"
                    f"📊 **포지션별 승률:**\n"
                    f"   🛡️ 탱커: {match_stats['tank_winrate']:.1f}% ({match_stats['tank_games']}경기)\n"
                    f"   ⚔️ 딜러: {match_stats['dps_winrate']:.1f}% ({match_stats['dps_games']}경기)\n"
                    f"   💚 힐러: {match_stats['support_winrate']:.1f}% ({match_stats['support_games']}경기)"
                )
                embed.add_field(
                    name="📈 내전 통계 (자동 수집)",
                    value=stats_info,
                    inline=False
                )
                
                # 최근 성과
                recent_matches = await self.bot.db_manager.get_recent_matches(user_id, guild_id, limit=5)
                if recent_matches:
                    recent_results = []
                    for match in recent_matches:
                        result = "🟢" if match['won'] else "🔴"
                        position_emoji = "🛡️" if match['position'] == "탱커" else "⚔️" if match['position'] == "딜러" else "💚"
                        recent_results.append(f"{result} {position_emoji} {match['position']}")
                    
                    embed.add_field(
                        name="🔥 최근 5경기",
                        value="\n".join(recent_results),
                        inline=True
                    )
                
                # 개인 랭킹
                rank_info = await self.bot.db_manager.get_user_server_rank(user_id, guild_id)
                if rank_info:
                    embed.add_field(
                        name="🏅 서버 랭킹",
                        value=f"전체 **{rank_info['rank']}위** / {rank_info['total_users']}명\n"
                              f"상위 **{rank_info['percentile']:.1f}%**",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📈 내전 통계",
                    value="아직 내전 참여 기록이 없습니다.\n내전에 참여하면 자동으로 통계가 수집됩니다!",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 정보 조회 중 오류: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="유저조회", description="다른 유저의 정보를 확인합니다")
    @app_commands.describe(유저="조회할 유저")
    async def user_lookup(
        self,
        interaction: discord.Interaction,
        유저: discord.Member
    ):
        target_user_id = str(유저.id)
        guild_id = str(interaction.guild_id)
        
        try:
            # 기본 정보
            guild_id = str(interaction.guild_id)
            user_data = await self.bot.db_manager.get_user_application(guild_id, target_user_id)
            if not user_data:
                await interaction.response.send_message(
                    f"❌ {유저.display_name}님의 등록 정보가 없습니다.",
                    ephemeral=True
                )
                return
            
            # 내전 통계 (요약만)
            match_stats = await self.bot.db_manager.get_detailed_user_stats(target_user_id, guild_id)
            
            embed = discord.Embed(
                title=f"👤 {유저.display_name}님의 정보",
                color=유저.color
            )
            embed.set_thumbnail(url=유저.display_avatar.url)
            
            # 공개 정보만 표시
            public_info = (
                f"🏷️ **배틀태그:** {user_data.get('battle_tag', 'N/A')}\n"
                f"🎮 **메인 포지션:** {user_data.get('main_position', 'N/A')}\n"
                f"🎯 **현재 티어:** {user_data.get('current_season_tier', 'N/A')}"
            )
            
            embed.add_field(
                name="📋 기본 정보",
                value=public_info,
                inline=False
            )
            
            # 내전 통계 요약 (5경기 이상일 때만 공개)
            if match_stats and match_stats['total_games'] >= 5:
                stats_summary = (
                    f"🎮 **총 경기:** {match_stats['total_games']}경기\n"
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}%\n"
                    f"⭐ **주요 포지션:** {self._get_most_played_position(match_stats)}"
                )
                
                embed.add_field(
                    name="📊 내전 통계",
                    value=stats_summary,
                    inline=False
                )
                
                # 서버 랭킹
                rank_info = await self.bot.db_manager.get_user_server_rank(target_user_id, guild_id)
                if rank_info:
                    embed.add_field(
                        name="🏅 서버 랭킹",
                        value=f"**{rank_info['rank']}위** / {rank_info['total_users']}명",
                        inline=True
                    )
                    
                # vs 기록 (요청자와의 대전 기록)
                vs_record = await self.bot.db_manager.get_head_to_head(
                    str(interaction.user.id), target_user_id, guild_id
                )
                if vs_record and vs_record['total_matches'] > 0:
                    embed.add_field(
                        name=f"⚔️ vs {interaction.user.display_name}",
                        value=f"{vs_record['wins']}승 {vs_record['losses']}패",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📊 내전 통계", 
                    value="통계 공개 기준 미충족 (5경기 이상 필요)",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 유저 조회 중 오류: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="순위표", description="서버 내 유저 랭킹을 확인합니다")
    @app_commands.describe(
        정렬기준="랭킹 정렬 기준",
        포지션="특정 포지션만 보기 (선택사항)"
    )
    @app_commands.choices(정렬기준=[
        app_commands.Choice(name="승률", value="winrate"),
        app_commands.Choice(name="총 경기수", value="games"),
        app_commands.Choice(name="승수", value="wins")
    ])
    @app_commands.choices(포지션=[
        app_commands.Choice(name="전체", value="all"),
        app_commands.Choice(name="탱커", value="tank"),
        app_commands.Choice(name="딜러", value="dps"),
        app_commands.Choice(name="힐러", value="support")
    ])
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        정렬기준: app_commands.Choice[str] = None,
        포지션: app_commands.Choice[str] = None
    ):
        sort_by = 정렬기준.value if 정렬기준 else "winrate"
        position_filter = 포지션.value if 포지션 else "all"
        guild_id = str(interaction.guild_id)
        
        try:
            # 랭킹 데이터 가져오기
            rankings = await self.bot.db_manager.get_server_rankings(
                guild_id=guild_id,
                sort_by=sort_by,
                position=position_filter,
                min_games=5  # 최소 5경기 이상
            )
            
            if not rankings:
                await interaction.response.send_message(
                    "📊 아직 랭킹 기준을 충족하는 유저가 없습니다.\n(최소 5경기 이상 필요)",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🏆 {interaction.guild.name} 랭킹",
                description=f"정렬: {정렬기준.name if 정렬기준 else '승률'} | "
                           f"포지션: {포지션.name if 포지션 else '전체'}",
                color=0xffd700
            )
            
            # 상위 10명 표시
            ranking_text = []
            for i, user_rank in enumerate(rankings[:10], 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                
                if sort_by == "winrate":
                    value = f"{user_rank['winrate']:.1f}%"
                elif sort_by == "games":
                    value = f"{user_rank['total_games']}경기"
                else:  # wins
                    value = f"{user_rank['wins']}승"
                
                ranking_text.append(
                    f"{medal} **{user_rank['username']}** | "
                    f"{user_rank['tier'] or 'N/A'} | "
                    f"{value} ({user_rank['total_games']}경기)"
                )
            
            embed.add_field(
                name="📋 순위표",
                value="\n".join(ranking_text),
                inline=False
            )
            
            # 본인 순위 표시
            user_rank = await self.bot.db_manager.get_user_server_rank(str(interaction.user.id), guild_id)
            if user_rank:
                embed.add_field(
                    name="🎯 내 순위",
                    value=f"**{user_rank['rank']}위** / {user_rank['total_users']}명 (상위 {user_rank['percentile']:.1f}%)",
                    inline=True
                )
            
            embed.set_footer(text="최소 5경기 이상 참여한 유저만 표시됩니다")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 순위표 조회 중 오류: {str(e)}",
                ephemeral=True
            )

    # 자동완성 함수들
    @update_info.autocomplete('현시즌티어')
    async def tier_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        tiers = [
            "브론즈5", "브론즈4", "브론즈3", "브론즈2", "브론즈1",
            "실버5", "실버4", "실버3", "실버2", "실버1", 
            "골드5", "골드4", "골드3", "골드2", "골드1",
            "플레5", "플레4", "플레3", "플레2", "플레1",
            "다이아5", "다이아4", "다이아3", "다이아2", "다이아1", 
            "마스터5", "마스터4", "마스터3", "마스터2", "마스터1",
            "그마5", "그마4", "그마3", "그마2", "그마1",
            "챔피언", "배치안함"
        ]
        
        if current:
            matching = [tier for tier in tiers if current.lower() in tier.lower()]
        else:
            matching = tiers[:25]
        
        return [
            app_commands.Choice(name=tier, value=tier)
            for tier in matching[:25]
        ]

    # 헬퍼 메서드들
    def _validate_battle_tag(self, battle_tag: str) -> bool:
        """배틀태그 형식 검증"""
        pattern = r'^[a-zA-Z가-힣0-9]{3,12}#[0-9]{4,5}$'
        return bool(re.match(pattern, battle_tag))
    
    def _get_most_played_position(self, stats: dict) -> str:
        """가장 많이 플레이한 포지션 반환"""
        positions = {
            "탱커": stats['tank_games'],
            "딜러": stats['dps_games'], 
            "힐러": stats['support_games']
        }
        
        if max(positions.values()) == 0:
            return "미정"
        
        return max(positions, key=positions.get)

async def setup(bot):
    await bot.add_cog(SimpleUserManagementCog(bot))