import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal, Optional, List
from datetime import datetime
import re

ALL_OVERWATCH_MAPS = [
    # 호위 맵 (8개)
    "66번국도", "지브롤터", "도라도", "리알토", "샴발리수도원", 
    "서킷로얄", "쓰레기촌", "하바나",
    
    # 밀기 맵 (4개)  
    "뉴 퀸 스트리트", "이스페란사", "콜로세오", "루나사피",
    
    # 혼합 맵 (7개)
    "눔바니", "미드타운", "블리자드 월드", "아이헨발데", 
    "왕의 길", "파라이수", "할리우드",
    
    # 쟁탈 맵 (7개)
    "일리오스", "리장타워", "네팔", "오아시스", 
    "부산", "남극반도", "사모아",
    
    # 플래시포인트 맵 (3개)
    "뉴 정크 시티", "수라바사", "아틀라스",
    
    # 격돌 맵 (2개)
    "아누비스의 왕좌", "하나오카"
]

class SimpleUserManagementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="유저정보수정", description="[관리자] 등록된 유저의 정보를 수정합니다")
    @app_commands.describe(
        유저명="수정할 유저명 (자동완성)",
        tier="현재 시즌 티어 (선택사항)",
        position="메인 포지션 (선택사항)",
        battle_tag="배틀태그 (선택사항)",
        birth_year="출생년도 뒤 2자리 (선택사항)"
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="언랭", value="언랭"),
        app_commands.Choice(name="브론즈", value="브론즈"),
        app_commands.Choice(name="실버", value="실버"),
        app_commands.Choice(name="골드", value="골드"),
        app_commands.Choice(name="플래티넘", value="플래티넘"),
        app_commands.Choice(name="다이아", value="다이아"),
        app_commands.Choice(name="마스터", value="마스터"),
        app_commands.Choice(name="그마", value="그마"),
        app_commands.Choice(name="챔피언", value="챔피언")
    ])
    @app_commands.choices(position=[
        app_commands.Choice(name="탱커", value="탱커"),
        app_commands.Choice(name="딜러", value="딜러"),
        app_commands.Choice(name="힐러", value="힐러"),
        app_commands.Choice(name="탱커 & 딜러", value="탱커 & 딜러"),
        app_commands.Choice(name="탱커 & 힐러", value="탱커 & 힐러"),
        app_commands.Choice(name="딜러 & 힐러", value="딜러 & 힐러"),
        app_commands.Choice(name="탱커 & 딜러 & 힐러", value="탱커 & 딜러 & 힐러")
    ])
    @app_commands.default_permissions(manage_guild=True)
    async def admin_update_user_info(
        self,
        interaction: discord.Interaction,
        유저명: str,
        tier: Optional[str] = None,
        position: Optional[str] = None,
        battle_tag: Optional[str] = None,
        birth_year: Optional[str] = None
    ):
        # 관리자 권한 체크
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 유저명으로 실제 유저 찾기
            registered_users = await self.bot.db_manager.get_registered_users_list(guild_id, 1000)
            target_user_data = None
            
            for user_data in registered_users:
                if user_data['username'].lower() == 유저명.lower():
                    target_user_data = user_data
                    break
            
            if not target_user_data:
                await interaction.followup.send(
                    f"❌ '{유저명}' 등록된 유저를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            user_id = target_user_data['user_id']
            
            # 생년 유효성 검증
            if birth_year:
                if len(birth_year) != 2 or not birth_year.isdigit():
                    await interaction.followup.send(
                        "❌ 생년은 숫자 2자리만 입력해주세요 (예: 00, 95)",
                        ephemeral=True
                    )
                    return
            
            # 현재 정보 조회
            current_info = await self.bot.db_manager.get_registered_user_info(guild_id, user_id)
            
            if not current_info:
                await interaction.followup.send(
                    "❌ 유저 정보를 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            # 변경할 정보만 업데이트 (제공된 것만)
            updates = {}
            if tier:
                updates['current_season_tier'] = tier
            if position:
                updates['main_position'] = position
            if birth_year:
                updates['birth_year'] = birth_year
            
            # 아무것도 변경하지 않은 경우
            if not updates and not battle_tag:
                await interaction.followup.send(
                    "❌ 수정할 정보를 하나 이상 입력해주세요.", ephemeral=True
                )
                return
            
            # DB 업데이트
            success = await self.bot.db_manager.update_registered_user_info(
                guild_id, user_id, updates
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 정보 수정에 실패했습니다.", ephemeral=True
                )
                return
            
            # 최종 정보 (변경된 것 + 기존 것)
            final_info = {
                'main_position': updates.get('main_position', current_info['main_position']),
                'current_season_tier': updates.get('current_season_tier', current_info['current_season_tier']),
                'birth_year': updates.get('birth_year', current_info.get('birth_year'))
            }
            
            # Discord 멤버 객체 찾기
            target_member = interaction.guild.get_member(int(user_id))

            # 닉네임용 배틀태그 결정
            nickname_battle_tag = None
            if battle_tag:
                # 직접 입력한 배틀태그 사용
                nickname_battle_tag = battle_tag
            else:
                # DB에서 주계정 조회
                nickname_battle_tag = await self.bot.db_manager._get_primary_battle_tag_for_nickname(
                    guild_id, user_id
                )
            
            # 닉네임 자동 변경 (멤버가 서버에 있는 경우만)
            nickname_result = "⚠️ 유저가 서버에 없어 닉네임을 변경할 수 없음"
            if target_member:
                nickname_result = await self.bot.db_manager._update_user_nickname(
                    target_member,
                    final_info['main_position'],
                    final_info['current_season_tier'],
                    nickname_battle_tag,
                    final_info['birth_year']
                )
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 유저 정보 수정 완료",
                description=f"**{유저명}**님의 정보가 수정되었습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # 변경 내역 표시
            changes = []
            if tier and tier != current_info['current_season_tier']:
                changes.append(f"**티어**: {current_info['current_season_tier']} → {tier}")
            
            if position and position != current_info['main_position']:
                changes.append(f"**포지션**: {current_info['main_position']} → {position}")
            
            if birth_year and birth_year != current_info.get('birth_year'):
                old_birth = current_info.get('birth_year', '미설정')
                changes.append(f"**생년**: {old_birth} → {birth_year}")

            if battle_tag:
                changes.append(f"**배틀태그**: {battle_tag} (지정됨)")
            
            if changes:
                embed.add_field(
                    name="📝 변경 내역",
                    value="\n".join(changes),
                    inline=False
                )
            
            # 닉네임 변경 결과
            embed.add_field(
                name="🔄 닉네임 자동 변경",
                value=nickname_result,
                inline=False
            )
            
            embed.add_field(
                name="📋 최종 정보",
                value=f"**포지션**: {final_info['main_position']}\n"
                    f"**현시즌 티어**: {final_info['current_season_tier']}\n"
                    f"**생년**: {final_info['birth_year'] or '미설정'}\n"
                    f"**닉네임 기준 배틀태그**: {nickname_battle_tag or '없음'}",
                inline=False
            )
            
            embed.set_footer(text=f"수정한 관리자: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # 대상 유저에게 DM 알림 (선택사항)
            if target_member:
                try:
                    dm_embed = discord.Embed(
                        title="📢 정보 수정 알림",
                        description=f"**{interaction.guild.name}** 서버에서 관리자가 회원님의 정보를 수정했습니다.",
                        color=0x0099ff
                    )
                    if changes:
                        dm_embed.add_field(
                            name="📝 변경 내역",
                            value="\n".join(changes),
                            inline=False
                        )
                    dm_embed.add_field(
                        name="ℹ️ 안내",
                        value="변경 내용에 문제가 있다면 관리자에게 문의해주세요.",
                        inline=False
                    )
                    await target_member.send(embed=dm_embed)
                except:
                    pass  # DM 실패해도 무시
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 정보 수정 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @admin_update_user_info.autocomplete('유저명')
    async def admin_update_user_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """등록된 유저들만 자동완성으로 표시"""
        try:
            guild_id = str(interaction.guild_id)
            registered_users = await self.bot.db_manager.get_registered_users_list(guild_id, 100)
            
            matching_users = []
            
            for user_data in registered_users:
                username = user_data['username']
                battle_tag = user_data.get('battle_tag', '')
                position = user_data.get('main_position', '')
                tier = user_data.get('current_season_tier', '')
                
                # 검색어 매칭
                if (current.lower() in username.lower() or 
                    current.lower() in battle_tag.lower() or
                    current == ""):
                    
                    display_name = f"{username} ({battle_tag}/{position}/{tier})"
                    
                    matching_users.append(
                        app_commands.Choice(
                            name=display_name[:100],
                            value=username
                        )
                    )
            
            return matching_users[:25]
            
        except Exception as e:
            print(f"[DEBUG] 자동완성 오류: {e}")
            return []

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)

    @app_commands.command(name="정보수정", description="내 정보를 수정합니다 (수정 시 닉네임 자동 변경)")
    @app_commands.describe(
        tier="현재 시즌 티어를 선택하세요",
        position="메인 포지션을 선택하세요 (선택사항)",
        battle_tag="배틀태그를 변경하려면 입력하세요 (선택사항)",
        birth_year="출생년도 뒤 2자리 (00, 95 등) (선택사항)"
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="언랭", value="언랭"),
        app_commands.Choice(name="브론즈", value="브론즈"),
        app_commands.Choice(name="실버", value="실버"),
        app_commands.Choice(name="골드", value="골드"),
        app_commands.Choice(name="플래티넘", value="플래티넘"),
        app_commands.Choice(name="다이아", value="다이아"),
        app_commands.Choice(name="마스터", value="마스터"),
        app_commands.Choice(name="그마", value="그마"),
        app_commands.Choice(name="챔피언", value="챔피언")
    ])
    @app_commands.choices(position=[
        app_commands.Choice(name="탱커", value="탱커"),
        app_commands.Choice(name="딜러", value="딜러"),
        app_commands.Choice(name="힐러", value="힐러"),
        app_commands.Choice(name="탱커 & 딜러", value="탱커 & 딜러"),
        app_commands.Choice(name="탱커 & 힐러", value="탱커 & 힐러"),
        app_commands.Choice(name="딜러 & 힐러", value="딜러 & 힐러"),
        app_commands.Choice(name="탱커 & 딜러 & 힐러", value="탱커 & 딜러 & 힐러")
    ])
    async def update_info(
        self,
        interaction: discord.Interaction,
        tier: str,
        position: Optional[str] = None,
        battle_tag: Optional[str] = None,
        birth_year: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 등록된 유저인지 확인
            if not await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "❌ 등록되지 않은 유저입니다. `/유저신청` 명령어로 먼저 가입 신청을 해주세요.",
                    ephemeral=True
                )
                return
            
            # 생년 유효성 검증
            if birth_year:
                if len(birth_year) != 2 or not birth_year.isdigit():
                    await interaction.followup.send(
                        "❌ 생년은 숫자 2자리만 입력해주세요 (예: 00, 95)",
                        ephemeral=True
                    )
                    return
            
            # 현재 정보 조회
            current_info = await self.bot.db_manager.get_registered_user_info(guild_id, user_id)
            
            if not current_info:
                await interaction.followup.send(
                    "❌ 유저 정보를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 닉네임용 배틀태그 결정
            nickname_battle_tag = None
            if battle_tag:
                # 직접 입력한 배틀태그 사용
                nickname_battle_tag = battle_tag
            else:
                # DB에서 주계정 조회
                nickname_battle_tag = await self.bot.db_manager._get_primary_battle_tag_for_nickname(
                    guild_id, user_id
                )
            
            # 변경할 정보 준비
            updates = {
                'current_season_tier': tier,
                'main_position': position if position else current_info['main_position']
            }
            
            if birth_year:
                updates['birth_year'] = birth_year

            # DB 업데이트
            success = await self.bot.db_manager.update_registered_user_info(
                guild_id, user_id, updates
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 정보 수정에 실패했습니다.",
                    ephemeral=True
                )
                return
            
            # 닉네임 자동 변경
            nickname_result = await self.bot.db_manager._update_user_nickname(
                interaction.user,
                updates['main_position'],
                updates['current_season_tier'],
                nickname_battle_tag, 
                birth_year
            )
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 정보 수정 완료",
                description="내 정보가 성공적으로 수정되었습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # 변경 내역 표시
            changes = []
            if tier != current_info['current_season_tier']:
                changes.append(f"**티어**: {current_info['current_season_tier']} → {tier}")
            
            if position and position != current_info['main_position']:
                changes.append(f"**포지션**: {current_info['main_position']} → {position}")

            if birth_year and birth_year != current_info.get('birth_year'):
                old_birth = current_info.get('birth_year', '미설정')
                changes.append(f"**생년**: {old_birth} → {birth_year}")
            
            if changes:
                embed.add_field(
                    name="📝 변경 내역",
                    value="\n".join(changes),
                    inline=False
                )
            
            # 닉네임 변경 결과
            embed.add_field(
                name="🔄 닉네임 자동 변경",
                value=nickname_result,
                inline=False
            )
            
            embed.add_field(
                name="💡 안내",
                value="배틀태그 추가/변경은 `/배틀태그추가` 명령어를 사용하세요",
                inline=False
            )
            
            embed.set_footer(text="내 정보 확인: /내정보 | 배틀태그 관리: /배틀태그목록")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 정보 수정 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="내정보", description="내 정보와 통계를 확인합니다")
    @app_commands.describe(보기="보기 옵션 (기본: 핵심 정보)")
    @app_commands.choices(보기=[
        app_commands.Choice(name="핵심", value="basic"),
        app_commands.Choice(name="상세", value="detailed"), 
        app_commands.Choice(name="팀", value="team")
    ])
    async def my_info(self, interaction: discord.Interaction, 보기: app_commands.Choice[str] = None):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        # 기본값 설정
        view_type = 보기.value if 보기 else "basic"
        
        if view_type == "basic":
            await self._show_basic_info(interaction, user_id, guild_id)
        elif view_type == "detailed":
            await self._show_detailed_info(interaction, user_id, guild_id)
        elif view_type == "team":
            await self._show_team_winrate_info(interaction, user_id, guild_id)

    @app_commands.command(name="유저조회", description="다른 유저의 정보를 조회합니다")
    @app_commands.describe(
        유저="조회할 유저",
        보기="보기 옵션 (기본: 핵심 정보)"
    )
    @app_commands.choices(보기=[
        app_commands.Choice(name="핵심", value="basic"),
        app_commands.Choice(name="상세", value="detailed"), 
        app_commands.Choice(name="팀", value="team")
    ])
    async def user_lookup(self, interaction: discord.Interaction, 유저: discord.Member, 보기: app_commands.Choice[str] = None):
        target_user_id = str(유저.id)
        guild_id = str(interaction.guild_id)
        
        # 기본값 설정
        view_type = 보기.value if 보기 else "basic"
        
        try:
            # 기본 정보 확인
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, target_user_id)
            if not user_data:
                await interaction.response.send_message(
                    f"❌ {유저.display_name}님의 등록 정보가 없습니다.",
                    ephemeral=True
                )
                return
            
            if view_type == "basic":
                await self._show_user_basic_info(interaction, 유저, target_user_id, guild_id)
            elif view_type == "detailed":
                await self._show_user_detailed_info(interaction, 유저, target_user_id, guild_id)
            elif view_type == "team":
                await self._show_user_team_winrate_info(interaction, 유저, target_user_id, guild_id)
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 유저 조회 중 오류: {str(e)}",
                ephemeral=True
            )

    async def _show_user_basic_info(self, interaction: discord.Interaction, target_user: discord.Member, target_user_id: str, guild_id: str):
        """다른 유저의 핵심 정보 표시 (베스트 페어 포함)"""
        try:
            # 기본 정보
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, target_user_id)
            
            # 내전 통계
            match_stats = await self.bot.db_manager.get_detailed_user_stats(target_user_id, guild_id)
            
            # 공개 기준 확인
            is_public = match_stats and match_stats['total_games'] >= 5
            
            embed = discord.Embed(
                title=f"👤 {target_user.display_name}님의 정보",
                color=target_user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # 📊 핵심 통계
            if is_public:
                core_stats = (
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}% ({match_stats['wins']}승 {match_stats['losses']}패)\n"
                    f"🎯 **주 포지션:** {user_data.get('main_position', 'N/A')} | **현재:** {user_data.get('current_season_tier', 'N/A')} | **최고:** {user_data.get('highest_tier', 'N/A')}"
                )
                
                # 서버 랭킹
                rank_info = await self.bot.db_manager.get_user_server_rank(target_user_id, guild_id)
                if rank_info:
                    core_stats += f"\n🥇 **서버 랭킹:** {rank_info['rank']}위 / {rank_info['total_users']}명 (상위 {rank_info['percentile']:.1f}%)"
            else:
                core_stats = (
                    f"🏆 **전체 승률:** 비공개 (최소 5경기 필요)\n"
                    f"🎯 **주 포지션:** {user_data.get('main_position', 'N/A')} | **현재:** {user_data.get('current_season_tier', 'N/A')} | **최고:** {user_data.get('highest_tier', 'N/A')}"
                )
            
            embed.add_field(
                name="📊 핵심 통계",
                value=core_stats,
                inline=False
            )
            
            # 🤝 베스트 페어 승률 (공개 기준 충족 시에만)
            if is_public:
                try:
                    best_pairs = await self.bot.db_manager.get_best_pairs_summary(target_user_id, guild_id)
                    
                    if best_pairs and (best_pairs.tank_pair or best_pairs.support_pair or best_pairs.dps_pair):
                        pair_lines = []
                        
                        if best_pairs.tank_pair:
                            pair = best_pairs.tank_pair
                            emoji = "🔥" if pair.winrate >= 75 else "⭐"
                            pair_lines.append(f"├ **탱커**: {pair.teammate_name} ({pair.winrate}% | {pair.total_games}경기) {emoji}")
                        
                        if best_pairs.support_pair:
                            pair = best_pairs.support_pair
                            emoji = "🔥" if pair.winrate >= 75 else "⭐"
                            pair_lines.append(f"├ **힐러**: {pair.teammate_name} ({pair.winrate}% | {pair.total_games}경기) {emoji}")
                        
                        if best_pairs.dps_pair:
                            pair = best_pairs.dps_pair
                            emoji = "🔥" if pair.winrate >= 75 else "⭐"
                            pair_lines.append(f"└ **딜러**: {pair.teammate_name} ({pair.winrate}% | {pair.total_games}경기) {emoji}")
                        
                        if pair_lines:
                            # 마지막 라인 조정
                            if len(pair_lines) > 1:
                                last_line = pair_lines[-1].replace("├", "└")
                                pair_lines[-1] = last_line
                            
                            embed.add_field(
                                name="🤝 베스트 페어 승률",
                                value="\n".join(pair_lines),
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="🤝 베스트 페어 승률", 
                            value="아직 베스트 페어 데이터가 부족합니다.",
                            inline=False
                        )
                except Exception as e:
                    print(f"베스트 페어 조회 오류: {e}")
            else:
                embed.add_field(
                    name="🤝 베스트 페어 승률", 
                    value="통계 공개 기준 미충족 (최소 5경기 필요)",
                    inline=False
                )
            
            # vs 기록 (요청자와의 대전 기록)
            if is_public:
                vs_record = await self.bot.db_manager.get_head_to_head(
                    str(interaction.user.id), target_user_id, guild_id
                )
                if vs_record and vs_record['total_matches'] > 0:
                    embed.add_field(
                        name=f"⚔️ vs {interaction.user.display_name}",
                        value=f"**{vs_record['wins']}승 {vs_record['losses']}패** ({vs_record['total_matches']}경기)",
                        inline=True
                    )
            
            # 📝 상세보기 안내
            if is_public:
                embed.add_field(
                    name="📝 더 자세한 정보",
                    value=f"📋 **상세 통계**: `/유저조회 @{target_user.display_name} 보기:상세`\n"
                        f"🤝 **팀 승률**: `/유저조회 @{target_user.display_name} 보기:팀`",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 5경기 이상 시 통계가 공개됩니다")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"유저 기본 정보 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ 유저 정보 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _show_user_detailed_info(self, interaction: discord.Interaction, target_user: discord.Member, target_user_id: str, guild_id: str):
        """다른 유저의 상세 정보 (프라이버시 고려)"""
        try:
            # 기본 정보
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, target_user_id)
            
            # 내전 통계 및 공개 기준 확인
            match_stats = await self.bot.db_manager.get_detailed_user_stats(target_user_id, guild_id)
            is_public = match_stats and match_stats['total_games'] >= 5
            
            embed = discord.Embed(
                title=f"👤 {target_user.display_name}님의 상세 정보",
                color=target_user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # 기본 정보 (항상 공개)
            basic_info = (
                f"🏷️ **배틀태그:** {user_data.get('battle_tag', 'N/A')}\n"
                f"🎮 **메인 포지션:** {user_data.get('main_position', 'N/A')}\n"
                f"🎯 **현재 티어:** {user_data.get('current_season_tier', 'N/A')}\n"
                f"⭐ **최고 티어:** {user_data.get('highest_tier', 'N/A')}"
            )
            
            embed.add_field(
                name="📋 기본 정보",
                value=basic_info,
                inline=False
            )
            
            # 통계 정보 (공개 기준 충족 시)
            if is_public:
                overall_stats = (
                    f"🎮 **총 경기:** {match_stats['total_games']}경기\n"
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}%\n"
                    f"📊 **전적:** {match_stats['wins']}승 {match_stats['losses']}패"
                )
                
                embed.add_field(
                    name="📊 내전 통계",
                    value=overall_stats,
                    inline=False
                )
                
                # 포지션별 통계 (간소화)
                position_stats = []
                if match_stats['tank_games'] > 0:
                    position_stats.append(f"🛡️ 탱커: {match_stats['tank_winrate']:.1f}% ({match_stats['tank_games']}경기)")
                if match_stats['dps_games'] > 0:
                    position_stats.append(f"⚔️ 딜러: {match_stats['dps_winrate']:.1f}% ({match_stats['dps_games']}경기)")  
                if match_stats['support_games'] > 0:
                    position_stats.append(f"💚 힐러: {match_stats['support_winrate']:.1f}% ({match_stats['support_games']}경기)")
                
                if position_stats:
                    embed.add_field(
                        name="🎯 포지션별 승률",
                        value="\n".join(position_stats),
                        inline=False
                    )
                
                # 특기 맵만 표시 (약점은 프라이버시상 숨김)
                try:
                    best_maps = await self.bot.db_manager.get_user_best_worst_maps(target_user_id, guild_id, limit=3)
                    if best_maps.get('best'):
                        best_list = [f"🔥 {m['map_name']} ({m['winrate']:.0f}%)" for m in best_maps['best']]
                        
                        embed.add_field(
                            name="🎯 특기 맵",
                            value="\n".join(best_list) if best_list else "데이터 부족",
                            inline=True
                        )
                except:
                    pass
                
                # 서버 랭킹
                rank_info = await self.bot.db_manager.get_user_server_rank(target_user_id, guild_id)
                if rank_info:
                    embed.add_field(
                        name="🥇 서버 랭킹",
                        value=f"**{rank_info['rank']}위** / {rank_info['total_users']}명\n(상위 {rank_info['percentile']:.1f}%)",
                        inline=True
                    )
                
                # vs 기록 (요청자와의 대전 기록)
                vs_record = await self.bot.db_manager.get_head_to_head(
                    str(interaction.user.id), target_user_id, guild_id
                )
                if vs_record and vs_record['total_matches'] > 0:
                    my_wins = vs_record.get('user1_wins', vs_record.get('wins', 0))
                    their_wins = vs_record.get('user2_wins', vs_record.get('losses', 0))
                    
                    embed.add_field(
                        name=f"⚔️ vs {interaction.user.display_name}",
                        value=f"**{their_wins}승 {my_wins}패** ({vs_record['total_matches']}경기)",
                        inline=True
                    )
                    
            else:
                embed.add_field(
                    name="📊 내전 통계", 
                    value="통계 공개 기준 미충족\n\n"
                        f"**현재:** {match_stats['total_games'] if match_stats else 0}경기\n"
                        "**공개 기준:** 5경기 이상",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 개인정보 보호를 위해 5경기 이상만 상세 공개됩니다")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"유저 상세 정보 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ {target_user.display_name}님의 상세 정보 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _show_user_team_winrate_info(self, interaction: discord.Interaction, target_user: discord.Member, target_user_id: str, guild_id: str):
        """다른 유저의 팀 승률 정보 - 프라이버시 고려"""
        try:
            # 기본 통계 확인 (공개 기준 체크)
            match_stats = await self.bot.db_manager.get_detailed_user_stats(target_user_id, guild_id)
            
            if not match_stats or match_stats['total_games'] < 5:
                await interaction.response.send_message(
                    f"❌ {target_user.display_name}님의 통계는 비공개입니다. (최소 5경기 필요)",
                    ephemeral=True
                )
                return
            
            # 팀 승률 분석
            team_analysis = await self.bot.db_manager.get_user_team_winrate_analysis(target_user_id, guild_id)
            
            if not team_analysis:
                await interaction.response.send_message(
                    f"❌ {target_user.display_name}님의 팀 승률 데이터를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🤝 {target_user.display_name}님의 팀 승률 분석",
                color=target_user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # 전체 팀 통계 요약
            total_team_games = team_analysis.get_total_team_games()
            overall_team_winrate = team_analysis.get_overall_team_winrate()
            
            if total_team_games == 0:
                embed.add_field(
                    name="📊 팀 승률 분석",
                    value="포지션 정보가 있는 팀 경기 데이터가 없습니다.",
                    inline=False
                )
                await interaction.response.send_message(embed=embed)
                return
            
            # 📊 전체 요약
            embed.add_field(
                name="📊 전체 팀 통계",
                value=f"🎮 **팀 경기 수:** {total_team_games}경기\n"
                    f"🏆 **전체 팀 승률:** {overall_team_winrate}%",
                inline=False
            )
            
            # 각 포지션별 상위 3명만 표시 (프라이버시 고려)
            sections_added = 0
            
            # 🛡️ 탱커 페어 - 상위 3명만
            if team_analysis.tank_pairs:
                tank_lines = []
                for i, pair in enumerate(team_analysis.tank_pairs[:3]):
                    rank_emoji = ["🥇", "🥈", "🥉"][i]
                    perf_emoji = " 🔥" if pair.winrate >= 70 else " ⚠️" if pair.winrate <= 40 else ""
                    tank_lines.append(f"{rank_emoji} {pair.teammate_name}: {pair.winrate}% ({pair.total_games}경기){perf_emoji}")
                
                if tank_lines:
                    embed.add_field(
                        name="🛡️ 탱커 페어 (Top 3)",
                        value="\n".join(tank_lines),
                        inline=True
                    )
                    sections_added += 1
            
            # 💚 힐러 페어 - 상위 3명만
            if team_analysis.support_pairs:
                support_lines = []
                for i, pair in enumerate(team_analysis.support_pairs[:3]):
                    rank_emoji = ["🥇", "🥈", "🥉"][i]
                    perf_emoji = " 🔥" if pair.winrate >= 70 else " ⚠️" if pair.winrate <= 40 else ""
                    support_lines.append(f"{rank_emoji} {pair.teammate_name}: {pair.winrate}% ({pair.total_games}경기){perf_emoji}")
                
                if support_lines:
                    embed.add_field(
                        name="💚 힐러 페어 (Top 3)",
                        value="\n".join(support_lines),
                        inline=True
                    )
                    sections_added += 1
            
            # ⚔️ 딜러 페어 - 상위 3명만
            if team_analysis.dps_pairs:
                dps_lines = []
                for i, pair in enumerate(team_analysis.dps_pairs[:3]):
                    rank_emoji = ["🥇", "🥈", "🥉"][i]
                    perf_emoji = " 🔥" if pair.winrate >= 70 else " ⚠️" if pair.winrate <= 40 else ""
                    dps_lines.append(f"{rank_emoji} {pair.teammate_name}: {pair.winrate}% ({pair.total_games}경기){perf_emoji}")
                
                if dps_lines:
                    embed.add_field(
                        name="⚔️ 딜러 페어 (Top 3)",
                        value="\n".join(dps_lines),
                        inline=True
                    )
                    sections_added += 1
            
            # 빈 필드로 레이아웃 정리
            while sections_added % 3 != 0:
                embed.add_field(name="\u200b", value="\u200b", inline=True)
                sections_added += 1
            
            embed.set_footer(text="개인정보 보호를 위해 상위 3명만 표시됩니다 | RallyUp Bot")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"유저 팀 승률 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ 팀 승률 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _show_basic_info(self, interaction: discord.Interaction, user_id: str, guild_id: str):
        """핵심 정보만 표시 (베스트 페어 요약 포함) - 완성된 버전"""
        try:
            # 기본 정보
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
                color=interaction.user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 📊 핵심 통계
            if match_stats and match_stats['total_games'] > 0:
                core_stats = (
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}% ({match_stats['wins']}승 {match_stats['losses']}패)\n"
                    f"🎯 **주 포지션:** {user_data.get('main_position', 'N/A')} | **현재:** {user_data.get('current_season_tier', 'N/A')} | **최고:** {user_data.get('highest_tier', 'N/A')}"
                )
            else:
                core_stats = (
                    f"🏆 **전체 승률:** 데이터 없음\n"
                    f"🎯 **주 포지션:** {user_data.get('main_position', 'N/A')} | **현재:** {user_data.get('current_season_tier', 'N/A')} | **최고:** {user_data.get('highest_tier', 'N/A')}"
                )
            
            # 서버 랭킹
            rank_info = await self.bot.db_manager.get_user_server_rank(user_id, guild_id)
            if rank_info:
                core_stats += f"\n🥇 **서버 랭킹:** {rank_info['rank']}위 / {rank_info['total_users']}명 (상위 {rank_info['percentile']:.1f}%)"
            
            embed.add_field(
                name="📊 핵심 통계",
                value=core_stats,
                inline=False
            )
            
            # 🤝 베스트 페어 승률 (새로 추가!)
            try:
                best_pairs = await self.bot.db_manager.get_best_pairs_summary(user_id, guild_id)
                
                if best_pairs and (best_pairs.tank_pair or best_pairs.support_pair or best_pairs.dps_pair):
                    pair_lines = []
                    
                    # 탱커 베스트 페어
                    if best_pairs.tank_pair:
                        pair = best_pairs.tank_pair
                        emoji = "🔥" if pair.winrate >= 75 else "⭐"
                        pair_lines.append(f"├ **탱커**: {pair.teammate_name} ({pair.winrate}% | {pair.wins}승 {pair.total_games - pair.wins}패) {emoji}")
                    
                    # 힐러 베스트 페어  
                    if best_pairs.support_pair:
                        pair = best_pairs.support_pair
                        emoji = "🔥" if pair.winrate >= 75 else "⭐"
                        pair_lines.append(f"├ **힐러**: {pair.teammate_name} ({pair.winrate}% | {pair.wins}승 {pair.total_games - pair.wins}패) {emoji}")
                    
                    # 딜러 베스트 페어
                    if best_pairs.dps_pair:
                        pair = best_pairs.dps_pair
                        emoji = "🔥" if pair.winrate >= 75 else "⭐"
                        symbol = "└" if not best_pairs.tank_pair and not best_pairs.support_pair else "└"
                        pair_lines.append(f"{symbol} **딜러**: {pair.teammate_name} ({pair.winrate}% | {pair.wins}승 {pair.total_games - pair.wins}패) {emoji}")
                    
                    if pair_lines:
                        # 마지막 라인의 기호를 └로 변경
                        if len(pair_lines) > 1:
                            last_line = pair_lines[-1].replace("├", "└")
                            pair_lines[-1] = last_line
                        
                        embed.add_field(
                            name="🤝 베스트 페어 승률",
                            value="\n".join(pair_lines),
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="🤝 베스트 페어 승률", 
                            value="아직 베스트 페어를 선정할 데이터가 부족합니다.",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="🤝 베스트 페어 승률", 
                        value="아직 페어 데이터가 충분하지 않습니다.\n\n"
                            "**필요 조건:**\n"
                            "• 포지션 정보가 포함된 내전 경기 참여\n"
                            "• 같은 파트너와 최소 3경기 이상\n"
                            "• `/내전포지션` 명령어로 기록된 경기",
                        inline=False
                    )
            except Exception as e:
                print(f"베스트 페어 조회 오류: {e}")
                embed.add_field(
                    name="🤝 베스트 페어 승률", 
                    value="데이터 로드 중 오류가 발생했습니다.\n나중에 다시 시도해주세요.",
                    inline=False
                )
            
            # 📝 상세보기 안내
            embed.add_field(
                name="📝 더 자세한 정보",
                value="📋 **상세 통계**: `/내정보 보기:상세`\n"
                    "🤝 **팀 승률**: `/내정보 보기:팀`\n"
                    "📊 **순위표**: `/순위표`",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 팀 승률은 포지션 정보가 있는 경기를 기준으로 계산됩니다")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"기본 정보 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ 정보 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _show_detailed_info(self, interaction: discord.Interaction, user_id: str, guild_id: str):
        """기존의 상세한 내정보 (모든 통계) - 완전한 구현"""
        try:
            # 기본 정보
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
                title=f"👤 {interaction.user.display_name}님의 상세 정보",
                color=interaction.user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            try:
                registered_at = user_data.get('registered_at')
                if registered_at:
                    try:
                        if 'T' in str(registered_at):
                            reg_date = datetime.fromisoformat(str(registered_at).replace('Z', '+00:00'))
                        else:
                            reg_date = datetime.strptime(str(registered_at), '%Y-%m-%d %H:%M:%S')
                        join_date_str = reg_date.strftime('%Y.%m.%d')
                    except Exception as e:
                        print(f"가입일 파싱 오류: {e}, 원본: {registered_at}")
                        join_date_str = str(registered_at)[:10]  # 앞 10자리만
                else:
                    join_date_str = "N/A"
            except Exception:
                join_date_str = "N/A"
            
            # 기본 정보 필드
            basic_info = (
                f"🏷️ **배틀태그:** {user_data.get('battle_tag', 'N/A')}\n"
                f"🎮 **메인 포지션:** {user_data.get('main_position', 'N/A')}\n"
                f"🎯 **현재 티어:** {user_data.get('current_season_tier', 'N/A')}\n"
                f"⭐ **최고 티어:** {user_data.get('highest_tier', 'N/A')}\n"
                f"📅 **가입일:** {join_date_str}"
            )
            
            embed.add_field(
                name="📋 기본 정보",
                value=basic_info,
                inline=False
            )
            
            # 내전 통계 필드
            if match_stats and match_stats['total_games'] > 0:
                overall_stats = (
                    f"🎮 **총 경기:** {match_stats['total_games']}경기\n"
                    f"🏆 **전체 승률:** {match_stats['overall_winrate']:.1f}%\n"
                    f"📊 **전적:** {match_stats['wins']}승 {match_stats['losses']}패"
                )
                
                embed.add_field(
                    name="📊 내전 통계",
                    value=overall_stats,
                    inline=False
                )
                
                # 포지션별 통계
                position_stats = []
                if match_stats['tank_games'] > 0:
                    position_stats.append(f"🛡️ **탱커:** {match_stats['tank_winrate']:.1f}% ({match_stats['tank_games']}경기)")
                if match_stats['dps_games'] > 0:
                    position_stats.append(f"⚔️ **딜러:** {match_stats['dps_winrate']:.1f}% ({match_stats['dps_games']}경기)")  
                if match_stats['support_games'] > 0:
                    position_stats.append(f"💚 **힐러:** {match_stats['support_winrate']:.1f}% ({match_stats['support_games']}경기)")
                
                if position_stats:
                    embed.add_field(
                        name="🎯 포지션별 승률",
                        value="\n".join(position_stats),
                        inline=False
                    )
                
                # 맵 타입별 성과 (상위 5개만)
                try:
                    map_stats = await self.bot.db_manager.get_user_map_type_stats(user_id, guild_id)
                    if map_stats:
                        map_lines = []
                        for map_stat in map_stats[:5]:  # 상위 5개만
                            emoji_map = {
                                "호위": "🚛", "밀기": "📦", "혼합": "🔄", 
                                "쟁탈": "🎯", "플래시포인트": "⚡", "격돌": "⚔️"
                            }
                            emoji = emoji_map.get(map_stat['map_type'], "🗺️")
                            map_lines.append(f"{emoji} **{map_stat['map_type']}:** {map_stat['winrate']:.1f}% ({map_stat['games']}경기)")
                        
                        embed.add_field(
                            name="🗺️ 맵 타입별 성과",
                            value="\n".join(map_lines) if map_lines else "데이터 없음",
                            inline=True
                        )
                except:
                    pass  # 맵 통계 오류 시 무시
                
                # 특기/약점 맵 (베스트/워스트 각 2개)
                try:
                    best_maps = await self.bot.db_manager.get_user_best_worst_maps(user_id, guild_id, limit=2)
                    if best_maps.get('best') or best_maps.get('worst'):
                        strength_weakness = []
                        
                        if best_maps.get('best'):
                            best_list = [f"🔥 {m['map_name']} ({m['winrate']:.0f}%)" for m in best_maps['best']]
                            strength_weakness.extend(best_list)
                        
                        if best_maps.get('worst'):
                            worst_list = [f"⚠️ {m['map_name']} ({m['winrate']:.0f}%)" for m in best_maps['worst']]  
                            strength_weakness.extend(worst_list)
                        
                        embed.add_field(
                            name="🎯 특기/약점 맵",
                            value="\n".join(strength_weakness[:4]) if strength_weakness else "데이터 부족",
                            inline=True
                        )
                except:
                    pass
                
                # 최근 경기 (5경기)
                try:
                    recent_matches = await self.bot.db_manager.get_user_recent_matches(user_id, guild_id, limit=5)
                    if recent_matches:
                        match_lines = []
                        for match in recent_matches:
                            # 승리/패배 이모지
                            status_emoji = "🏆" if match['won'] else "💔"
                            
                            # 포지션 이모지 매핑 (더 포괄적으로)
                            position = str(match.get('position', '')).lower()
                            if '탱' in position or 'tank' in position:
                                position_emoji = "🛡️"
                            elif '딜' in position or 'dps' in position or 'damage' in position:
                                position_emoji = "⚔️"
                            elif '힐' in position or 'support' in position or 'heal' in position:
                                position_emoji = "💚"
                            else:
                                position_emoji = "❓"
                                # 디버깅을 위해 실제 position 값 출력
                                print(f"알 수 없는 포지션: '{match.get('position')}'")
                            
                            # 날짜 파싱 (더 안전하게)
                            date_str = "?"
                            try:
                                match_date_raw = match.get('match_date', '')
                                if match_date_raw:
                                    # 다양한 날짜 형식 처리
                                    match_date_str = str(match_date_raw).strip()
                                    
                                    if 'T' in match_date_str:
                                        if match_date_str.endswith('Z'):
                                            match_date_str = match_date_str.replace('Z', '+00:00')
                                        match_date = datetime.fromisoformat(match_date_str)
                                    elif len(match_date_str) >= 10:
                                        if ' ' in match_date_str:
                                            match_date = datetime.strptime(match_date_str[:19], '%Y-%m-%d %H:%M:%S')
                                        else:
                                            match_date = datetime.strptime(match_date_str[:10], '%Y-%m-%d')
                                    else:
                                        raise ValueError(f"Unknown date format: {match_date_str}")
                                    
                                    date_str = match_date.strftime("%m/%d")
                                    
                            except Exception as e:
                                print(f"날짜 파싱 실패: {e}, 원본 데이터: {match.get('match_date')}")
                                date_str = "날짜오류"
                            
                            match_lines.append(f"{status_emoji} {position_emoji} {date_str}\n")
                        
                        embed.add_field(
                            name="🔥 최근 5경기",
                            value=" ".join(match_lines) if match_lines else "경기 없음",
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="🔥 최근 5경기",
                            value="경기 기록이 없습니다.",
                            inline=True
                        )
                except Exception as e:
                    print(f"최근 경기 조회 오류: {e}")
                    embed.add_field(
                        name="🔥 최근 5경기",
                        value="데이터 로드 중 오류가 발생했습니다.",
                        inline=True
                    )
                
                try:
                    rank_info = await self.bot.db_manager.get_user_server_rank(user_id, guild_id)
                    if rank_info:
                        embed.add_field(
                            name="🏅 서버 랭킹",
                            value=f"전체 **{rank_info['rank']}위** / {rank_info['total_users']}명\n"
                                f"상위 **{rank_info['percentile']:.1f}%**",
                            inline=True
                        )
                except Exception as e:
                    print(f"서버 랭킹 조회 오류: {e}")
            else:
                embed.add_field(
                    name="📈 내전 통계",
                    value="아직 내전 참여 기록이 없습니다.\n내전에 참여하면 해당 통계가 수집됩니다!",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 상세 통계는 5경기 이상부터 공개됩니다")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"상세 정보 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ 상세 정보 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def _show_team_winrate_info(self, interaction: discord.Interaction, user_id: str, guild_id: str):
        """팀 승률 전용 정보 - 완전한 구현"""
        try:
            # 팀 승률 분석
            team_analysis = await self.bot.db_manager.get_user_team_winrate_analysis(user_id, guild_id)
            
            if not team_analysis:
                await interaction.response.send_message(
                    "❌ 팀 승률 데이터를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 기본 정보 확인
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, user_id)
            username = interaction.user.display_name if not user_data else user_data.get('username', interaction.user.display_name)
            
            embed = discord.Embed(
                title=f"🤝 {username}님의 팀 승률 분석",
                color=interaction.user.color,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            # 전체 팀 통계 요약
            total_team_games = team_analysis.get_total_team_games()
            overall_team_winrate = team_analysis.get_overall_team_winrate()
            
            if total_team_games == 0:
                embed.add_field(
                    name="📊 팀 승률 분석",
                    value="아직 포지션 정보가 있는 팀 경기 데이터가 없습니다.\n\n"
                        "**필요한 조건:**\n"
                        "• 포지션 정보가 기록된 내전 경기\n"
                        "• `/내전포지션` 명령어로 기록된 경기\n"
                        "• 최소 1경기 이상",
                    inline=False
                )
                
                embed.add_field(
                    name="💡 팀 승률을 확인하려면",
                    value="1. 내전 경기 참여\n"
                        "2. `/내전결과` 명령어로 결과 기록\n"
                        "3. `/내전포지션` 명령어로 포지션 정보 추가\n"
                        "4. 다시 `/내정보 보기:팀` 확인",
                    inline=False
                )
                
                await interaction.response.send_message(embed=embed)
                return
            
            # 📊 전체 요약
            embed.add_field(
                name="📊 전체 팀 통계",
                value=f"🎮 **팀 경기 수:** {total_team_games}경기\n"
                    f"🏆 **전체 팀 승률:** {overall_team_winrate}%\n"
                    f"📈 **분석 기준:** 함께 플레이한 모든 경기",
                inline=False
            )
            
            # 🛡️ 탱커 페어 (내가 딜러/힐러일 때 함께한 탱커들)
            if team_analysis.tank_pairs:
                tank_lines = []
                for i, pair in enumerate(team_analysis.tank_pairs[:7]):  # 상위 7명
                    # 이모지 및 순위 표시
                    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣"][i] if i < 7 else "📍"
                    perf_emoji = ""
                    
                    if pair.winrate >= 80:
                        perf_emoji = " 🔥🔥"
                    elif pair.winrate >= 70:
                        perf_emoji = " 🔥"
                    elif pair.winrate >= 60:
                        perf_emoji = " ✨"
                    elif pair.winrate <= 30:
                        perf_emoji = " ⚠️"
                    elif pair.winrate <= 40:
                        perf_emoji = " 📉"
                    
                    tank_lines.append(f"{rank_emoji} **{pair.teammate_name}**: {pair.winrate}% ({pair.wins}승 {pair.total_games - pair.wins}패){perf_emoji}")
                
                embed.add_field(
                    name="🛡️ 탱커 페어 승률",
                    value="\n".join(tank_lines) if tank_lines else "데이터 없음",
                    inline=False
                )
            else:
                embed.add_field(
                    name="🛡️ 탱커 페어 승률",
                    value="딜러나 힐러로 플레이한 경기가 없습니다.",
                    inline=False
                )
            
            # 💚 힐러 페어 (내가 힐러일 때 함께한 힐러들)
            if team_analysis.support_pairs:
                support_lines = []
                for i, pair in enumerate(team_analysis.support_pairs[:7]):  # 상위 7명
                    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣"][i] if i < 7 else "📍"
                    perf_emoji = ""
                    
                    if pair.winrate >= 80:
                        perf_emoji = " 🔥🔥"
                    elif pair.winrate >= 70:
                        perf_emoji = " 🔥"
                    elif pair.winrate >= 60:
                        perf_emoji = " ✨"
                    elif pair.winrate <= 30:
                        perf_emoji = " ⚠️"
                    elif pair.winrate <= 40:
                        perf_emoji = " 📉"
                    
                    support_lines.append(f"{rank_emoji} **{pair.teammate_name}**: {pair.winrate}% ({pair.wins}승 {pair.total_games - pair.wins}패){perf_emoji}")
                
                embed.add_field(
                    name="💚 힐러 페어 승률",
                    value="\n".join(support_lines) if support_lines else "데이터 없음",
                    inline=False
                )
            else:
                embed.add_field(
                    name="💚 힐러 페어 승률",
                    value="힐러로 플레이한 경기가 없습니다.",
                    inline=False
                )
            
            # ⚔️ 딜러 페어 (내가 딜러일 때 함께한 딜러들)
            if team_analysis.dps_pairs:
                dps_lines = []
                for i, pair in enumerate(team_analysis.dps_pairs[:7]):  # 상위 7명
                    rank_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣"][i] if i < 7 else "📍"
                    perf_emoji = ""
                    
                    if pair.winrate >= 80:
                        perf_emoji = " 🔥🔥"
                    elif pair.winrate >= 70:
                        perf_emoji = " 🔥"
                    elif pair.winrate >= 60:
                        perf_emoji = " ✨"
                    elif pair.winrate <= 30:
                        perf_emoji = " ⚠️"
                    elif pair.winrate <= 40:
                        perf_emoji = " 📉"
                    
                    dps_lines.append(f"{rank_emoji} **{pair.teammate_name}**: {pair.winrate}% ({pair.wins}승 {pair.total_games - pair.wins}패){perf_emoji}")
                
                embed.add_field(
                    name="⚔️ 딜러 페어 승률",
                    value="\n".join(dps_lines) if dps_lines else "데이터 없음",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚔️ 딜러 페어 승률", 
                    value="딜러로 플레이한 경기가 없습니다.",
                    inline=False
                )
            
            # 🎯 인사이트 및 팁
            insights = []
            
            # 베스트 파트너 찾기
            best_overall = None
            best_winrate = 0
            best_category = ""
            
            all_pairs = []
            if team_analysis.tank_pairs:
                all_pairs.extend([(pair, "탱커") for pair in team_analysis.tank_pairs])
            if team_analysis.support_pairs:
                all_pairs.extend([(pair, "힐러") for pair in team_analysis.support_pairs])
            if team_analysis.dps_pairs:
                all_pairs.extend([(pair, "딜러") for pair in team_analysis.dps_pairs])
            
            # 최소 3경기 이상, 최고 승률 파트너
            for pair, category in all_pairs:
                if pair.total_games >= 3 and pair.winrate > best_winrate:
                    best_overall = pair
                    best_winrate = pair.winrate
                    best_category = category
            
            if best_overall:
                insights.append(f"🌟 **최고 파트너**: {best_overall.teammate_name} ({best_category}, {best_overall.winrate}%)")
            
            # 가장 많이 함께 플레이한 파트너
            most_played_partner = None
            most_games = 0
            for pair, category in all_pairs:
                if pair.total_games > most_games:
                    most_played_partner = pair
                    most_games = pair.total_games
            
            if most_played_partner:
                insights.append(f"🤝 **단짝 파트너**: {most_played_partner.teammate_name} ({most_games}경기 함께)")
            
            # 개선이 필요한 파트너
            worst_qualified = None
            worst_winrate = 100
            for pair, category in all_pairs:
                if pair.total_games >= 3 and pair.winrate < worst_winrate:
                    worst_qualified = pair
                    worst_winrate = pair.winrate
            
            if worst_qualified and worst_winrate < 40:
                insights.append(f"📈 **개선 필요**: {worst_qualified.teammate_name}와 더 연습이 필요해보입니다")
            
            if insights:
                embed.add_field(
                    name="🎯 인사이트",
                    value="\n".join(insights),
                    inline=False
                )
            
            embed.set_footer(text="💡 3경기 이상 함께 플레이한 파트너만 순위에 반영됩니다 | RallyUp Bot")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"팀 승률 조회 오류: {e}")
            await interaction.response.send_message(
                f"❌ 팀 승률 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="맵통계", description="서버 전체 맵 플레이 통계를 확인합니다")
    @app_commands.describe(
        타입="특정 맵 타입만 보기 (선택사항)",
        분석="표시할 분석 유형 (선택사항)"
    )
    @app_commands.choices(타입=[
        app_commands.Choice(name="전체", value="all"),
        app_commands.Choice(name="호위", value="호위"),
        app_commands.Choice(name="쟁탈", value="쟁탈"),
        app_commands.Choice(name="혼합", value="혼합"),
        app_commands.Choice(name="밀기", value="밀기"),
        app_commands.Choice(name="플래시포인트", value="플래시포인트"),
        app_commands.Choice(name="격돌", value="격돌")
    ])
    @app_commands.choices(분석=[
        app_commands.Choice(name="전체 요약", value="overview"),
        app_commands.Choice(name="인기 맵", value="popularity"),
        app_commands.Choice(name="맵 밸런스", value="balance"),
        app_commands.Choice(name="맵 메타", value="meta")
    ])
    async def map_statistics(
        self,
        interaction: discord.Interaction,
        타입: app_commands.Choice[str] = None,
        분석: app_commands.Choice[str] = None
    ):
        guild_id = str(interaction.guild_id)
        map_type = 타입.value if 타입 else "all"
        analysis_type = 분석.value if 분석 else "overview"
        
        await interaction.response.defer()
        
        try:
            # 기본 개요 정보는 항상 조회
            overview = await self.bot.db_manager.get_server_map_overview(guild_id)
            
            if not overview or overview['total_matches'] == 0:
                await interaction.followup.send(
                    "📊 아직 맵 정보가 포함된 경기 기록이 없습니다.\n"
                    "맵 정보를 포함해서 경기를 기록하면 통계가 생성됩니다!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🗺️ 서버 맵 통계",
                description=f"**{interaction.guild.name}** 맵 플레이 분석",
                color=0x00ff88
            )
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            
            # 맵 타입 필터 정보 표시
            type_text = "전체 맵 타입" if map_type == "all" else f"{map_type} 맵"
            embed.add_field(
                name="🔍 분석 범위",
                value=f"**맵 타입:** {type_text}\n**분석 유형:** {분석.name if 분석 else '전체 요약'}",
                inline=False
            )
            
            if analysis_type == "overview":
                # 전체 요약
                overview_text = (
                    f"📊 **총 경기 수:** {overview['total_matches']:,}경기\n"
                    f"🗺️ **플레이된 맵:** {overview['unique_maps']}개\n"
                    f"📁 **맵 타입:** {overview['unique_map_types']}종류"
                )
                embed.add_field(
                    name="📈 전체 현황",
                    value=overview_text,
                    inline=False
                )
                
                # 맵 타입별 분포
                if overview['type_distribution']:
                    distribution_lines = []
                    for dist in overview['type_distribution'][:6]:  # 상위 6개만
                        emoji = {
                            "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                            "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                        }.get(dist['map_type'], "🗺️")
                        
                        distribution_lines.append(
                            f"{emoji} **{dist['map_type']}**: {dist['count']}경기 ({dist['percentage']}%)"
                        )
                    
                    embed.add_field(
                        name="📊 맵 타입별 분포",
                        value="\n".join(distribution_lines),
                        inline=False
                    )
            
            elif analysis_type == "popularity":
                # 인기 맵 랭킹
                popularity = await self.bot.db_manager.get_server_map_popularity(guild_id, map_type, 10)
                
                if popularity:
                    popularity_lines = []
                    for i, map_data in enumerate(popularity, 1):
                        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                        emoji = {
                            "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                            "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                        }.get(map_data['map_type'], "🗺️")
                        
                        popularity_lines.append(
                            f"{medal} {emoji} **{map_data['map_name']}** "
                            f"- {map_data['play_count']}경기 ({map_data['play_percentage']}%)"
                        )
                    
                    embed.add_field(
                        name="🏆 인기 맵 TOP 10",
                        value="\n".join(popularity_lines),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🏆 인기 맵",
                        value="해당 맵 타입의 데이터가 부족합니다.",
                        inline=False
                    )
            
            elif analysis_type == "balance":
                # 맵 밸런스 분석
                balance = await self.bot.db_manager.get_server_map_balance(guild_id, 3)
                
                if balance:
                    balance_lines = []
                    for map_data in balance[:10]:  # 상위 10개만
                        emoji = {
                            "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                            "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                        }.get(map_data['map_type'], "🗺️")
                        
                        balance_emoji = {
                            "완벽": "🟢", "좋음": "🟡", "보통": "🟠", "불균형": "🔴"
                        }.get(map_data['balance_rating'], "⚪")
                        
                        balance_lines.append(
                            f"{emoji} **{map_data['map_name']}** "
                            f"{balance_emoji}{map_data['balance_rating']} "
                            f"(A{map_data['team_a_winrate']}% vs B{map_data['team_b_winrate']}%)"
                        )
                    
                    embed.add_field(
                        name="⚖️ 맵 밸런스 분석 (3경기 이상)",
                        value="\n".join(balance_lines),
                        inline=False
                    )
                    
                    embed.add_field(
                        name="📋 밸런스 등급 설명",
                        value="🟢완벽: ±5% | 🟡좋음: ±10% | 🟠보통: ±20% | 🔴불균형: ±20%+",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⚖️ 맵 밸런스",
                        value="밸런스 분석을 위한 데이터가 부족합니다. (최소 3경기 필요)",
                        inline=False
                    )
            
            elif analysis_type == "meta":
                # 맵 메타 분석
                meta = await self.bot.db_manager.get_server_map_meta(guild_id, 5)
                
                if meta:
                    meta_text = []
                    for map_data in meta[:5]:  # 상위 5개 맵만
                        emoji = {
                            "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                            "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                        }.get(map_data['map_type'], "🗺️")
                        
                        # 해당 맵에서 가장 승률이 높은 포지션
                        best_position = max(map_data['positions'], key=lambda x: x['winrate'])
                        pos_emoji = "🛡️" if best_position['position'] == "탱커" else "⚔️" if best_position['position'] == "딜러" else "💚"
                        
                        meta_text.append(
                            f"{emoji} **{map_data['map_name']}**: "
                            f"{pos_emoji}{best_position['position']} {best_position['winrate']}% "
                            f"({best_position['games']}경기)"
                        )
                    
                    embed.add_field(
                        name="🎯 맵별 최고 성과 포지션 (5경기 이상)",
                        value="\n".join(meta_text),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🎯 맵 메타 분석",
                        value="메타 분석을 위한 데이터가 부족합니다. (최소 5경기 필요)",
                        inline=False
                    )
            
            # 추가 옵션 안내
            embed.add_field(
                name="💡 다른 분석 보기",
                value="`/맵통계 분석:인기맵` - 인기 맵 랭킹\n"
                    "`/맵통계 분석:맵밸런스` - A팀 vs B팀 승률 분석\n"
                    "`/맵통계 분석:맵메타` - 포지션별 승률 분석\n"
                    "`/맵통계 타입:호위` - 특정 맵 타입만 분석",
                inline=False
            )
            
            embed.set_footer(text="💡 /맵분석 @유저 명령어로 개인 맵 분석도 가능합니다!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 맵 통계 조회 중 오류: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="맵분석", description="특정 유저의 맵별 상세 분석을 확인합니다")
    @app_commands.describe(
        유저="분석할 유저 (미입력시 본인)",
        맵타입="특정 맵 타입만 분석"
    )
    @app_commands.choices(맵타입=[
        app_commands.Choice(name="전체", value="all"),
        app_commands.Choice(name="호위", value="호위"),
        app_commands.Choice(name="밀기", value="밀기"),
        app_commands.Choice(name="혼합", value="혼합"),
        app_commands.Choice(name="쟁탈", value="쟁탈"),
        app_commands.Choice(name="플래시포인트", value="플래시포인트"),
        app_commands.Choice(name="격돌", value="격돌")
    ])
    async def map_analysis(
        self,
        interaction: discord.Interaction,
        유저: discord.Member = None,
        맵타입: app_commands.Choice[str] = None
    ):
        # 분석 대상 유저 결정
        target_user = 유저 if 유저 else interaction.user
        target_user_id = str(target_user.id)
        guild_id = str(interaction.guild_id)
        map_type_filter = 맵타입.value if 맵타입 else "all"
        
        await interaction.response.defer()
        
        try:
            # 기본 정보 확인
            user_data = await self.bot.db_manager.get_registered_user_info(guild_id, target_user_id)
            if not user_data:
                await interaction.followup.send(
                    f"❌ {target_user.display_name}님의 등록 정보가 없습니다.",
                    ephemeral=True
                )
                return
            
            # 상세 맵별 통계 조회
            detailed_map_stats = await self.bot.db_manager.get_user_detailed_map_stats(
                target_user_id, guild_id, map_type_filter
            )
            
            if not detailed_map_stats:
                await interaction.followup.send(
                    f"❌ {target_user.display_name}님의 맵 플레이 기록이 없습니다.",
                    ephemeral=True
                )
                return
            
            # Embed 생성
            embed = discord.Embed(
                title=f"🗺️ {target_user.display_name}님의 맵 분석",
                description=f"분석 범위: {맵타입.name if 맵타입 else '전체'} 맵",
                color=target_user.color
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # 🗺️ 맵별 상세 성과 (상위 10개만 표시)
            if detailed_map_stats:
                map_performance = []
                for i, stat in enumerate(detailed_map_stats[:10]):  # 상위 10개만
                    # 맵 타입별 이모지
                    type_emoji = {
                        "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                        "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                    }.get(stat['map_type'], "🗺️")
                    
                    performance_emoji = "🔥" if stat['winrate'] >= 70 else "✅" if stat['winrate'] >= 50 else "📉"
                    
                    map_performance.append(
                        f"{performance_emoji} **{stat['map_name']}** {type_emoji} | "
                        f"{stat['winrate']}% ({stat['wins']}승 {stat['games']-stat['wins']}패)"
                    )
                
                embed.add_field(
                    name="🗺️ 맵별 성과 (상위 10개)",
                    value="\n".join(map_performance),
                    inline=False
                )
            
            # 📊 포지션-맵타입 매트릭스
            position_matrix = await self.bot.db_manager.get_user_position_map_matrix(target_user_id, guild_id)
            if position_matrix:
                matrix_data = {}
                for stat in position_matrix:
                    if stat['position'] not in matrix_data:
                        matrix_data[stat['position']] = {}
                    matrix_data[stat['position']][stat['map_type']] = stat
                
                matrix_lines = []
                positions = ["탱커", "딜러", "힐러"]
                map_types = ["호위", "밀기", "혼합", "쟁탈", "플래시포인트", "격돌"]
                
                for position in positions:
                    if position in matrix_data:
                        pos_emoji = "🛡️" if position == "탱커" else "⚔️" if position == "딜러" else "💚"
                        line = f"{pos_emoji} **{position}**: "
                        
                        type_results = []
                        for map_type in map_types:
                            if map_type in matrix_data[position] and matrix_data[position][map_type]['games'] >= 2:
                                stat = matrix_data[position][map_type]
                                type_emoji = {
                                    "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                                    "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                                }.get(map_type, "🗺️")
                                type_results.append(f"{type_emoji}{stat['winrate']}%")
                        
                        if type_results:
                            line += " | ".join(type_results)
                            matrix_lines.append(line)
                
                if matrix_lines:
                    embed.add_field(
                        name="📊 포지션별 맵타입 성과",
                        value="\n".join(matrix_lines),
                        inline=False
                    )
            
            # 💡 개선 제안
            improvements = await self.bot.db_manager.get_map_improvement_suggestions(target_user_id, guild_id)
            if improvements:
                improvement_lines = []
                
                if 'weak_type' in improvements:
                    weak = improvements['weak_type']
                    type_emoji = {
                        "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                        "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                    }.get(weak['map_type'], "🗺️")
                    improvement_lines.append(
                        f"📈 **{weak['map_type']}** {type_emoji} 맵 연습 필요 ({weak['winrate']}% 승률)"
                    )
                
                if 'weak_map' in improvements:
                    weak = improvements['weak_map']
                    improvement_lines.append(
                        f"🎯 **{weak['map_name']}** 맵 집중 연습 추천 ({weak['winrate']}% 승률)"
                    )
                
                if 'weak_combo' in improvements:
                    weak = improvements['weak_combo']
                    pos_emoji = "🛡️" if weak['position'] == "탱커" else "⚔️" if weak['position'] == "딜러" else "💚"
                    type_emoji = {
                        "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                        "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                    }.get(weak['map_type'], "🗺️")
                    improvement_lines.append(
                        f"{pos_emoji}{type_emoji} **{weak['position']}+{weak['map_type']}** 조합 개선 필요 ({weak['winrate']}% 승률)"
                    )
                
                if improvement_lines:
                    embed.add_field(
                        name="💡 개선 제안",
                        value="\n".join(improvement_lines),
                        inline=False
                    )
            
            # 👥 추천 팀원 (해당 맵타입에서 잘하는 사람들)
            recommended_teammates = await self.bot.db_manager.get_map_teammates_recommendations(
                target_user_id, guild_id, map_type_filter if map_type_filter != "all" else None
            )
            if recommended_teammates:
                teammate_lines = []
                for i, teammate in enumerate(recommended_teammates[:5], 1):  # 상위 5명
                    if map_type_filter != "all":
                        teammate_lines.append(
                            f"{i}. **{teammate['username']}** | {teammate['winrate']}% ({teammate['games']}경기)"
                        )
                    else:
                        type_emoji = {
                            "호위": "🚛", "밀기": "⚡", "혼합": "🔄", 
                            "쟁탈": "🎯", "플래시포인트": "💥", "격돌": "⚔️"
                        }.get(teammate['map_type'], "🗺️")
                        teammate_lines.append(
                            f"{i}. **{teammate['username']}** {type_emoji} | {teammate['winrate']}% ({teammate['games']}경기)"
                        )
                
                embed.add_field(
                    name="👥 추천 팀원",
                    value="\n".join(teammate_lines),
                    inline=False
                )
            
            # 통계 요약 정보
            total_maps_played = len(detailed_map_stats)
            total_games = sum(stat['games'] for stat in detailed_map_stats)
            total_wins = sum(stat['wins'] for stat in detailed_map_stats)
            overall_winrate = (total_wins / total_games * 100) if total_games > 0 else 0
            
            embed.add_field(
                name="📈 분석 요약",
                value=f"플레이한 맵: **{total_maps_played}개**\n"
                    f"총 경기수: **{total_games}경기**\n"
                    f"전체 승률: **{overall_winrate:.1f}%**",
                inline=True
            )
            
            embed.set_footer(
                text=f"분석 기준: 2경기 이상 플레이한 맵/조합만 표시 | 분석 시점: {interaction.created_at.strftime('%Y-%m-%d')}"
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 맵 분석 중 오류: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="순위표", description="서버 내 사용자 랭킹을 확인합니다")
    @app_commands.choices(정렬기준=[
        app_commands.Choice(name="승률 기준", value="winrate"),
        app_commands.Choice(name="경기 수 기준", value="games"),
        app_commands.Choice(name="승리 수 기준", value="wins"),
        app_commands.Choice(name="호위 맵 승률", value="escort_winrate"),
        app_commands.Choice(name="쟁탈 맵 승률", value="control_winrate"),
        app_commands.Choice(name="혼합 맵 승률", value="hybrid_winrate"),
        app_commands.Choice(name="밀기 맵 승률", value="push_winrate"),
        app_commands.Choice(name="플래시포인트 맵 승률", value="flashpoint_winrate"),
        app_commands.Choice(name="격돌 맵 승률", value="clash_winrate")
    ])
    @app_commands.choices(포지션=[
        app_commands.Choice(name="전체", value="all"),
        app_commands.Choice(name="탱커", value="tank"),
        app_commands.Choice(name="딜러", value="dps"),
        app_commands.Choice(name="힐러", value="support")
    ])
    @app_commands.choices(표시범위=[
        app_commands.Choice(name="🏆 상위 10명", value="top10"),
        app_commands.Choice(name="📍 내 주변 순위", value="around_me"),
        app_commands.Choice(name="📊 하위 10명", value="bottom10"),
        app_commands.Choice(name="📋 전체 순위 (1-50위)", value="all")
    ])
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        정렬기준: app_commands.Choice[str] = None,
        포지션: app_commands.Choice[str] = None,
        특정맵: str = None,
        표시범위: app_commands.Choice[str] = None
    ):
        sort_by = 정렬기준.value if 정렬기준 else "winrate"
        position_filter = 포지션.value if 포지션 else "all"
        specific_map = 특정맵 if 특정맵 else None
        display_range = 표시범위.value if 표시범위 else "top10"
        guild_id = str(interaction.guild_id)
        
        try:
            if 특정맵:
                if 특정맵 not in ALL_OVERWATCH_MAPS:
                    await interaction.response.send_message(
                        f"❌ '{특정맵}'은(는) 존재하지 않는 맵입니다.\n"
                        f"자동완성을 이용해 정확한 맵 이름을 입력해주세요.",
                        ephemeral=True
                    )
                    return
                
                rankings = await self.bot.db_manager.get_server_specific_map_rankings(
                    guild_id=guild_id,
                    map_name=특정맵,
                    min_games=3
                )
                ranking_title = f"🗺️ {특정맵} 맵 랭킹"
                min_games_text = "3경기"
            else:
                rankings = await self.bot.db_manager.get_server_rankings(
                    guild_id=guild_id,
                    sort_by=sort_by,
                    position=position_filter,
                    min_games=5 if not sort_by.endswith('_winrate') else 3
                )
                
                if sort_by.endswith('_winrate'):
                    map_type_names = {
                        'escort_winrate': '호위',
                        'control_winrate': '쟁탈', 
                        'hybrid_winrate': '혼합',
                        'push_winrate': '밀기',
                        'flashpoint_winrate': '플래시포인트',
                        'clash_winrate': '격돌'
                    }
                    map_type = map_type_names.get(sort_by, '맵')
                    ranking_title = f"🗺️ {map_type} 맵 랭킹"
                    min_games_text = "3경기"
                else:
                    ranking_title = f"🏆 {interaction.guild.name} 랭킹"
                    min_games_text = "5경기"
            
            if not rankings:
                await interaction.response.send_message(
                    f"📊 아직 랭킹 기준을 충족하는 유저가 없습니다.\n(최소 {min_games_text} 이상 필요)",
                    ephemeral=True
                )
                return
            
            # 표시 범위에 따른 데이터 필터링
            display_rankings = []
            range_description = ""
            
            if display_range == "top10":
                display_rankings = rankings[:10]
                range_description = "상위 10명"
            elif display_range == "bottom10":
                display_rankings = rankings[-10:] if len(rankings) > 10 else rankings
                range_description = f"하위 10명 ({len(rankings)-9}위~{len(rankings)}위)"
                # 역순 정렬 제거 - 14위부터 23위 순서로 표시
            elif display_range == "around_me":
                user_rank = await self.bot.db_manager.get_user_server_rank(
                    str(interaction.user.id), guild_id, position=position_filter
                )
                if user_rank and user_rank['rank'] <= len(rankings):
                    idx = user_rank['rank'] - 1  # 0-based index
                    start = max(0, idx - 5)
                    end = min(len(rankings), idx + 6)
                    display_rankings = rankings[start:end]
                    range_description = f"내 주변 순위 ({max(start+1, 1)}위~{min(end, len(rankings))}위)"
                else:
                    display_rankings = rankings[:10]
                    range_description = "상위 10명 (본인 랭킹 없음)"
            elif display_range == "all":
                display_rankings = rankings  # 최대 50명
                range_description = f"전체 순위 (1~{len(rankings)}위)"
            
            embed = discord.Embed(
                title=f"{ranking_title} - {range_description}",
                color=0xffd700
            )
            
            # 설명 텍스트 생성
            desc_parts = []
            desc_parts.append(f"정렬: {정렬기준.name if 정렬기준 else '승률'}")
            
            if 포지션 and 포지션.value != "all":
                desc_parts.append(f"포지션: {포지션.name}")
            
            if specific_map:
                desc_parts.append(f"맵: {specific_map}")
                
            embed.description = " | ".join(desc_parts)
            
            # 순위 표시 (표시 범위에 따라 순위 계산)
            ranking_text = []
            
            for i, user_rank in enumerate(display_rankings):
                # 실제 순위 계산
                if display_range == "top10":
                    actual_rank = i + 1
                elif display_range == "bottom10":
                    # 하위 10명 시작 순위 계산 (14위부터 시작)
                    start_rank = len(rankings) - len(display_rankings) + 1
                    actual_rank = start_rank + i
                elif display_range == "around_me":
                    # 내 주변 순위일 경우 시작 순위 계산
                    user_rank_info = await self.bot.db_manager.get_user_server_rank(
                        str(interaction.user.id), guild_id, position=position_filter
                    )
                    if user_rank_info:
                        actual_rank = max(1, user_rank_info['rank'] - 5) + i
                    else:
                        actual_rank = i + 1
                elif display_range == "all":
                    actual_rank = i + 1
                else:
                    actual_rank = i + 1
                
                # 메달 이모지 및 순위 표시 (Discord 자동 번호 매기기 방지)
                if display_range == "top10":
                    medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}위**"
                else:
                    medal = f"**{actual_rank}위**"
                
                # 본인 순위 강조
                username = user_rank['username']
                if user_rank['user_id'] == str(interaction.user.id):
                    username = f"⭐ **{username}**"
                
                # 맵별 랭킹일 때는 게임수와 승률 표시 방식 변경
                if specific_map or sort_by.endswith('_winrate'):
                    # 맵별 랭킹: 승률 우선 표시
                    value = f"{user_rank['winrate']}%"
                    games_info = f"({user_rank['wins']}승 {user_rank['games']-user_rank['wins']}패)"
                else:
                    # 일반 랭킹: 기존 방식 유지
                    if sort_by == "winrate":
                        value = f"{user_rank['winrate']}%"
                        games_info = f"({user_rank['total_games']}경기)"
                    elif sort_by == "games":
                        value = f"{user_rank['total_games']}경기"
                        games_info = f"({user_rank['winrate']}%)"
                    else:  # wins
                        value = f"{user_rank['wins']}승"
                        games_info = f"({user_rank['total_games']}경기)"
                
                ranking_text.append(
                    f"{medal} {username} • {user_rank['tier'] or 'N/A'} • {value} {games_info}"
                )
            
            # Embed 필드 길이 체크 (디스코드 제한: 1024자)
            ranking_text_str = "\n".join(ranking_text)
            if len(ranking_text_str) > 1024:
                # 너무 길면 반으로 나눠서 두 개 필드로 표시
                mid_point = len(display_rankings) // 2
                embed.add_field(
                    name="📋 순위표 (1/2)",
                    value="\n".join(ranking_text[:mid_point]),
                    inline=False
                )
                embed.add_field(
                    name="📋 순위표 (2/2)",
                    value="\n".join(ranking_text[mid_point:]),
                    inline=False
                )
            else:
                embed.add_field(
                    name="📋 순위표",
                    value=ranking_text_str,
                    inline=False
                )
            
            # 본인 순위 표시 (맵별 랭킹이 아니고, "내 주변 순위"가 아닐 때만)
            if not specific_map and not sort_by.endswith('_winrate') and display_range != "around_me":
                user_rank = await self.bot.db_manager.get_user_server_rank(
                    str(interaction.user.id), guild_id, position=position_filter
                )
                if user_rank:
                    embed.add_field(
                        name="🎯 내 순위",
                        value=f"**{user_rank['rank']}위** / {user_rank['total_users']}명 (상위 {user_rank['percentile']:.1f}%)",
                        inline=True
                    )
            
            # Footer 메시지 (하위권일 때 격려 메시지)
            footer_text = f"최소 {min_games_text} 이상 참여한 유저만 표시됩니다"
            if display_range == "bottom10":
                footer_text += " | 💪 경기 수를 늘려 순위를 올려보세요!"
            
            embed.set_footer(text=footer_text)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 순위표 조회 중 오류: {str(e)}",
                ephemeral=True
            )

    @leaderboard.autocomplete('특정맵')
    async def map_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        """맵 이름 자동완성"""
        
        # 현재 입력된 텍스트와 매칭되는 맵들 필터링
        if current:
            matching_maps = [
                map_name for map_name in ALL_OVERWATCH_MAPS 
                if current.lower() in map_name.lower()
            ]
        else:
            # 입력이 없으면 인기 맵들 먼저 표시
            matching_maps = [
                "눔바니", "리장타워", "66번국도", "지브롤터", "일리오스", 
                "네팔", "오아시스", "아이헨발데", "왕의 길", "할리우드"
            ]
        
        # Discord 제한에 맞춰 최대 25개만 반환
        return [
            app_commands.Choice(name=map_name, value=map_name)
            for map_name in matching_maps[:25]
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