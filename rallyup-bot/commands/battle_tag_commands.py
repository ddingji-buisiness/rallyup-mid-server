import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict, Optional, List
from datetime import datetime
from utils.battle_tag_logger import BattleTagLogger

class BattleTagCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = BattleTagLogger(bot)
    
    @app_commands.command(name="배틀태그추가", description="배틀태그를 추가합니다 (오버워치 랭크 정보 자동 조회)")
    @app_commands.describe(
        배틀태그="배틀태그 (예: 이름#1234)",
        계정타입="계정 타입을 선택하세요"
    )
    @app_commands.choices(계정타입=[
        app_commands.Choice(name="본계정", value="main"),
        app_commands.Choice(name="부계정", value="sub")
    ])
    async def add_battle_tag(
        self,
        interaction: discord.Interaction,
        배틀태그: str,
        계정타입: str = "sub"
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
            
            # 배틀태그 형식 검증
            from utils.helpers import validate_battle_tag_format
            
            if not validate_battle_tag_format(배틀태그):
                await interaction.followup.send(
                    "❌ 올바르지 않은 배틀태그 형식입니다.\n"
                    "**형식**: `이름#1234` (예: backyerin#3538)",
                    ephemeral=True
                )
                return
            
            # 배틀태그 추가 + API 호출
            success, rank_info = await self.bot.db_manager.add_battle_tag_with_api(
                guild_id, user_id, 배틀태그, 계정타입
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ 배틀태그 추가 실패\n"
                    f"• 이미 등록된 배틀태그일 수 있습니다.\n"
                    f"• `/배틀태그목록`으로 확인해보세요.",
                    ephemeral=True
                )
                return
            
            user_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            is_primary = len(user_tags) == 1  # 첫 배틀태그면 주계정
            
            await self.logger.log_battle_tag_add(
                guild_id=guild_id,
                user=interaction.user,
                battle_tag=배틀태그,
                account_type=계정타입,
                is_primary=is_primary,
                rank_info=rank_info
            )
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 배틀태그 추가 완료",
                description=f"**{배틀태그}**가 추가되었습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📋 계정 정보",
                value=f"**계정 타입**: {계정타입}\n"
                      f"**배틀태그**: {배틀태그}",
                inline=False
            )
            
            # API 랭크 정보 표시
            if rank_info:
                from utils.overwatch_api import OverwatchAPI
                rank_display = OverwatchAPI.format_rank_display(rank_info)
                
                embed.add_field(
                    name="🎮 오버워치 정보",
                    value=rank_display,
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚠️ 오버워치 정보",
                    value="프로필을 찾을 수 없거나 비공개 설정되어 있습니다.\n"
                          "랭크 정보 없이 배틀태그만 저장되었습니다.",
                    inline=False
                )
            
            # 첫 배틀태그인 경우 주계정으로 자동 설정 안내
            user_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            if len(user_tags) == 1:
                embed.add_field(
                    name="ℹ️ 자동 설정",
                    value="첫 번째 배틀태그로 **주계정 자동 설정**되었습니다.\n"
                          "닉네임 변경은 `/정보수정`으로 가능합니다.",
                    inline=False
                )
            
            embed.set_footer(text="배틀태그 목록: /배틀태그목록")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 배틀태그 추가 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="배틀태그목록", description="배틀태그 목록을 확인합니다 (오버워치 랭크 정보 포함)")
    @app_commands.describe(유저="조회할 유저 (선택사항 - 기본: 본인)")
    async def list_battle_tags(
        self,
        interaction: discord.Interaction,
        유저: Optional[discord.Member] = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 조회 대상 결정
            target_user = 유저 if 유저 else interaction.user
            user_id = str(target_user.id)
            
            # 등록된 유저인지 확인
            if not await self.bot.db_manager.is_user_registered(guild_id, user_id):
                if target_user == interaction.user:
                    await interaction.followup.send(
                        "❌ 등록되지 않은 유저입니다. `/유저신청` 명령어로 먼저 가입 신청을 해주세요.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ **{target_user.display_name}**님은 등록되지 않은 유저입니다.",
                        ephemeral=True
                    )
                return
            
            # 배틀태그 목록 조회
            tags = await self.bot.db_manager.get_user_battle_tags_with_rank(guild_id, user_id)
            
            if not tags:
                if target_user == interaction.user:
                    await interaction.followup.send(
                        "📝 등록된 배틀태그가 없습니다.\n"
                        "`/배틀태그추가` 명령어로 추가하세요.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"📝 **{target_user.display_name}**님은 등록된 배틀태그가 없습니다.",
                        ephemeral=True
                    )
                return
            
            # 메인 목록 임베드
            embed = discord.Embed(
                title=f"🎮 {target_user.display_name}님의 배틀태그",
                description=f"총 **{len(tags)}개** 계정",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text="RallyUp Bot | 상세보기 버튼을 눌러 랭크 정보 확인")
            
            # View 생성 (버튼 포함)
            view = BattleTagListView(
                self.bot, guild_id, user_id, tags, target_user, interaction.user
            )
            
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 배틀태그 목록 조회 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="배틀태그삭제", description="등록된 배틀태그를 삭제합니다")
    @app_commands.describe(배틀태그="삭제할 배틀태그 (자동완성)")
    async def delete_battle_tag(
        self,
        interaction: discord.Interaction,
        배틀태그: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 등록된 유저인지 확인
            if not await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "❌ 등록되지 않은 유저입니다.",
                    ephemeral=True
                )
                return
            
            tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            target_tag = next((t for t in tags if t['battle_tag'] == 배틀태그), None)
            
            if not target_tag:
                await interaction.followup.send(
                    f"❌ **{배틀태그}** 삭제 실패\n등록되지 않은 배틀태그입니다.",
                    ephemeral=True
                )
                return
            
            was_primary = target_tag['is_primary']
            
            # 배틀태그 삭제
            success = await self.bot.db_manager.delete_battle_tag(guild_id, user_id, 배틀태그)
            
            if not success:
                await interaction.followup.send(
                    f"❌ **{배틀태그}** 삭제 실패\n"
                    f"등록되지 않은 배틀태그이거나 이미 삭제되었습니다.",
                    ephemeral=True
                )
                return
            
            # 삭제 후 남은 배틀태그 확인
            remaining_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            new_primary = next((t for t in remaining_tags if t['is_primary']), None)
            
            await self.logger.log_battle_tag_delete(
                guild_id=guild_id,
                user=interaction.user,
                battle_tag=배틀태그,
                was_primary=was_primary,
                new_primary_tag=new_primary['battle_tag'] if new_primary else None
            )
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ 배틀태그 삭제 완료",
                description=f"**{배틀태그}**가 삭제되었습니다",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            
            # 남은 배틀태그 확인
            remaining_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            
            if remaining_tags:
                # 주계정이 자동으로 다른 계정으로 변경되었는지 확인
                new_primary = next((t for t in remaining_tags if t['is_primary']), None)
                if new_primary:
                    embed.add_field(
                        name="🔄 주계정 자동 변경",
                        value=f"주계정이 **{new_primary['battle_tag']}**로 변경되었습니다.",
                        inline=False
                    )
                
                embed.add_field(
                    name="📋 남은 배틀태그",
                    value=f"{len(remaining_tags)}개",
                    inline=True
                )
            else:
                embed.add_field(
                    name="⚠️ 안내",
                    value="모든 배틀태그가 삭제되었습니다.\n"
                          "`/배틀태그추가`로 새 배틀태그를 추가하세요.",
                    inline=False
                )
            
            embed.set_footer(text="배틀태그 목록: /배틀태그목록")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 배틀태그 삭제 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @delete_battle_tag.autocomplete('배틀태그')
    async def delete_battle_tag_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """본인의 배틀태그만 자동완성"""
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            
            matching = []
            for tag in tags:
                battle_tag = tag['battle_tag']
                
                if current.lower() in battle_tag.lower() or current == "":
                    # 주계정 표시
                    display = f"{'⭐' if tag['is_primary'] else '💫'} {battle_tag} ({tag['account_type']})"
                    
                    matching.append(
                        app_commands.Choice(
                            name=display[:100],
                            value=battle_tag
                        )
                    )
            
            return matching[:25]
            
        except Exception:
            return []
    
    @app_commands.command(name="주계정설정", description="주계정 배틀태그를 변경합니다 (닉네임 생성 기준)")
    @app_commands.describe(배틀태그="주계정으로 설정할 배틀태그 (자동완성)")
    async def set_primary_battle_tag(
        self,
        interaction: discord.Interaction,
        배틀태그: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 등록된 유저인지 확인
            if not await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "❌ 등록되지 않은 유저입니다.",
                    ephemeral=True
                )
                return
            
            old_primary = await self.bot.db_manager.get_primary_battle_tag(guild_id, user_id)
            
            # 주계정 설정
            success = await self.bot.db_manager.set_primary_battle_tag(guild_id, user_id, 배틀태그)
            
            if not success:
                await interaction.followup.send(
                    f"❌ 주계정 설정 실패\n"
                    f"**{배틀태그}**가 등록되어 있지 않습니다.",
                    ephemeral=True
                )
                return
            
            tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            new_primary_tag = next((t for t in tags if t['battle_tag'] == 배틀태그), None)
            
            if old_primary and old_primary != 배틀태그:  # 실제로 변경된 경우만
                await self.logger.log_primary_change(
                    guild_id=guild_id,
                    user=interaction.user,
                    old_primary=old_primary,
                    new_primary=배틀태그,
                    new_rank_info=new_primary_tag.get('rank_info') if new_primary_tag else None
                )
            
            # 성공 메시지
            embed = discord.Embed(
                title="⭐ 주계정 설정 완료",
                description=f"**{배틀태그}**가 주계정으로 설정되었습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="ℹ️ 주계정이란?",
                value="• 닉네임 생성 시 사용되는 배틀태그\n"
                      "• `/정보수정`으로 닉네임을 변경할 수 있습니다",
                inline=False
            )
            
            embed.add_field(
                name="💡 닉네임 변경 방법",
                value="`/정보수정 tier=그마` 처럼 티어 정보를 수정하면\n"
                      "주계정 배틀태그 기준으로 닉네임이 자동 변경됩니다.",
                inline=False
            )
            
            embed.set_footer(text="배틀태그 목록: /배틀태그목록")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 주계정 설정 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @set_primary_battle_tag.autocomplete('배틀태그')
    async def set_primary_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """주계정이 아닌 배틀태그만 자동완성"""
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            
            matching = []
            for tag in tags:
                battle_tag = tag['battle_tag']
                
                if current.lower() in battle_tag.lower() or current == "":
                    # 현재 주계정 강조
                    if tag['is_primary']:
                        display = f"⭐ {battle_tag} (현재 주계정)"
                    else:
                        display = f"💫 {battle_tag} ({tag['account_type']})"
                    
                    matching.append(
                        app_commands.Choice(
                            name=display[:100],
                            value=battle_tag
                        )
                    )
            
            return matching[:25]
            
        except Exception:
            return []
    
    @app_commands.command(name="배틀태그갱신", description="배틀태그의 오버워치 랭크 정보를 갱신합니다")
    @app_commands.describe(배틀태그="갱신할 배틀태그 (자동완성 - 선택사항, 없으면 전체 갱신)")
    async def refresh_battle_tag(
        self,
        interaction: discord.Interaction,
        배틀태그: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            
            # 등록된 유저인지 확인
            if not await self.bot.db_manager.is_user_registered(guild_id, user_id):
                await interaction.followup.send(
                    "❌ 등록되지 않은 유저입니다.",
                    ephemeral=True
                )
                return
            
            # 갱신 대상 결정
            if 배틀태그:
                # 특정 배틀태그만 갱신
                rank_info = await self.bot.db_manager.refresh_battle_tag_rank(
                    guild_id, user_id, 배틀태그
                )
                
                if rank_info:
                    from utils.overwatch_api import OverwatchAPI
                    rank_display = OverwatchAPI.format_rank_display(rank_info)
                    
                    embed = discord.Embed(
                        title="🔄 랭크 정보 갱신 완료",
                        description=f"**{배틀태그}** 정보가 업데이트되었습니다",
                        color=0x00ff88
                    )
                    embed.add_field(name="🎮 오버워치 정보", value=rank_display, inline=False)
                else:
                    embed = discord.Embed(
                        title="⚠️ 랭크 정보 갱신 실패",
                        description=f"**{배틀태그}** 프로필을 찾을 수 없거나 비공개 설정되어 있습니다.",
                        color=0xffaa00
                    )
            else:
                # 전체 배틀태그 갱신
                tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
                
                if not tags:
                    await interaction.followup.send(
                        "❌ 등록된 배틀태그가 없습니다.",
                        ephemeral=True
                    )
                    return
                
                success_count = 0
                for tag in tags:
                    rank_info = await self.bot.db_manager.refresh_battle_tag_rank(
                        guild_id, user_id, tag['battle_tag']
                    )
                    if rank_info:
                        success_count += 1
                
                embed = discord.Embed(
                    title="🔄 전체 랭크 정보 갱신 완료",
                    description=f"{success_count}/{len(tags)}개 배틀태그 업데이트 성공",
                    color=0x00ff88
                )
                embed.add_field(
                    name="📋 결과",
                    value=f"✅ 성공: {success_count}개\n"
                          f"⚠️ 실패: {len(tags) - success_count}개 (비공개 또는 없는 계정)",
                    inline=False
                )
            
            embed.set_footer(text="배틀태그 목록: /배틀태그목록")
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 랭크 정보 갱신 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @refresh_battle_tag.autocomplete('배틀태그')
    async def refresh_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """배틀태그 자동완성 (갱신용)"""
        return await self.delete_battle_tag_autocomplete(interaction, current)

    @app_commands.command(name="배틀태그검색", description="[관리자] 배틀태그로 소유자를 검색합니다 (역검색)")
    @app_commands.describe(배틀태그="검색할 배틀태그")
    @app_commands.default_permissions(manage_guild=True)
    async def search_battle_tag(
        self,
        interaction: discord.Interaction,
        배틀태그: str
    ):
        # 관리자 권한 확인
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # 배틀태그 소유자 검색
            owner_info = await self.bot.db_manager.search_battle_tag_owner(guild_id, 배틀태그)
            
            if not owner_info:
                await interaction.followup.send(
                    f"🔍 **{배틀태그}**\n\n"
                    f"이 배틀태그를 사용하는 유저를 찾을 수 없습니다.",
                    ephemeral=True
                )
                return
            
            # 소유자 정보 조회
            user_id = owner_info['user_id']
            username = owner_info['username']
            account_type = owner_info['account_type']
            is_primary = owner_info['is_primary']
            
            # Discord 멤버 객체
            member = interaction.guild.get_member(int(user_id))
            
            embed = discord.Embed(
                title="🔍 배틀태그 검색 결과",
                description=f"**{배틀태그}**의 소유자를 찾았습니다",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="👤 소유자 정보",
                value=f"**이름**: {username}\n"
                    f"**멘션**: <@{user_id}>\n"
                    f"**상태**: {'서버 있음' if member else '서버 없음'}",
                inline=False
            )
            
            embed.add_field(
                name="🎮 계정 정보",
                value=f"**계정 타입**: {account_type}\n"
                    f"**주계정 여부**: {'⭐ 주계정' if is_primary else '부계정'}",
                inline=False
            )
            
            # 해당 유저의 모든 배틀태그 조회
            all_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            
            if all_tags:
                tag_list = []
                for tag in all_tags[:5]:  # 최대 5개
                    emoji = "⭐" if tag['is_primary'] else "💫"
                    tag_list.append(f"{emoji} {tag['battle_tag']} ({tag['account_type']})")
                
                if len(all_tags) > 5:
                    tag_list.append(f"... 외 {len(all_tags) - 5}개")
                
                embed.add_field(
                    name=f"📋 {username}님의 전체 배틀태그 ({len(all_tags)}개)",
                    value="\n".join(tag_list),
                    inline=False
                )
            
            # 관리 액션
            embed.add_field(
                name="🔧 관리 액션",
                value=f"• `/유저정보수정 {username}` - 유저 정보 수정\n"
                    f"• `/배틀태그목록 @{username}` - 전체 배틀태그 확인",
                inline=False
            )
            
            if member:
                embed.set_thumbnail(url=member.display_avatar.url)
            
            embed.set_footer(text="RallyUp Bot | 관리자 전용")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 배틀태그 검색 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인 (서버 소유자 또는 DB 등록 관리자)"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)


    @app_commands.command(name="유저배틀태그", description="[관리자] 특정 유저의 모든 배틀태그를 조회합니다")
    @app_commands.describe(유저="조회할 유저")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_user_battle_tags(
        self,
        interaction: discord.Interaction,
        유저: discord.Member
    ):
        # 관리자 권한 확인
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        # 기존 /배틀태그목록 로직 재사용
        await self.list_battle_tags.__call__(interaction, 유저=유저)

class BattleTagListView(discord.ui.View):
    """배틀태그 목록 View (요약 + 버튼)"""
    
    def __init__(self, bot, guild_id: str, user_id: str, tags: List[Dict], 
                 target_user: discord.Member, requester: discord.Member):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.tags = tags
        self.target_user = target_user
        self.requester = requester
        
        # 드롭다운 추가
        if tags:
            self.add_item(BattleTagSelectDropdown(self))
        
        # 전체 새로고침 버튼
        if tags:
            refresh_all_btn = discord.ui.Button(
                label="전체 새로고침",
                style=discord.ButtonStyle.success,
                emoji="🔄",
                custom_id="refresh_all"
            )
            refresh_all_btn.callback = self.refresh_all_ranks
            self.add_item(refresh_all_btn)
    
    async def refresh_all_ranks(self, interaction: discord.Interaction):
        """모든 배틀태그 랭크 정보 새로고침"""
        await interaction.response.defer()
        
        success_count = 0
        for tag in self.tags:
            rank_info = await self.bot.db_manager.refresh_battle_tag_rank(
                self.guild_id, self.user_id, tag['battle_tag']
            )
            if rank_info:
                success_count += 1
        
        # 업데이트된 목록 재조회
        self.tags = await self.bot.db_manager.get_user_battle_tags_with_rank(
            self.guild_id, self.user_id
        )
        
        # 새로운 메인 임베드 생성
        embed = self.create_main_embed()
        embed.description += f"\n\n✅ {success_count}/{len(self.tags)}개 계정 갱신 완료"
        
        # View 재생성
        new_view = BattleTagListView(
            self.bot, self.guild_id, self.user_id, self.tags,
            self.target_user, self.requester
        )
        
        await interaction.edit_original_response(embed=embed, view=new_view)
    
    def create_main_embed(self) -> discord.Embed:
        """메인 목록 임베드 생성 (랭크 정보 포함)"""
        embed = discord.Embed(
            title=f"🎮 {self.target_user.display_name}님의 배틀태그",
            description=f"총 **{len(self.tags)}개** 계정 등록됨",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 각 배틀태그를 필드로 추가 (간략 정보)
        for tag in self.tags:
            emoji = "⭐" if tag['is_primary'] else "💫"
            account_type = "주계정" if tag['is_primary'] else f"{tag['account_type']}"
            
            # 랭크 정보 간략 표시
            if tag['rank_info'] and tag['rank_info'].get('ratings'):
                # 가장 높은 랭크만 표시
                ratings = tag['rank_info']['ratings']
                rank_parts = []
                for rating in ratings[:2]:  # 최대 2개만
                    role = rating.get('role', '').replace('offense', '딜러').replace('damage', '딜러')
                    role_kr = {'tank': '탱', 'damage': '딜', '딜러': '딜', 'support': '힐'}.get(role, role)
                    group = rating.get('group', '')
                    tier = rating.get('tier', '')
                    
                    tier_kr = {
                        'Bronze': '브', 'Silver': '실', 'Gold': '골',
                        'Platinum': '플', 'Diamond': '다', 'Master': '마',
                        'Grandmaster': '그마', 'Champion': '챔'
                    }.get(group, group)
                    
                    if tier_kr and tier:
                        rank_parts.append(f"{role_kr}:{tier_kr}{tier}")
                
                rank_summary = " | ".join(rank_parts) if rank_parts else "미배치"
            else:
                rank_summary = "랭크 정보 없음"
            
            embed.add_field(
                name=f"{emoji} {tag['battle_tag']}",
                value=f"**{account_type}** • {rank_summary}",
                inline=False
            )
        
        embed.set_thumbnail(url=self.target_user.display_avatar.url)
        embed.set_footer(text="아래 드롭다운에서 배틀태그를 선택하여 상세정보 확인")
        
        return embed

class BattleTagSelectDropdown(discord.ui.Select):
    """배틀태그 선택 드롭다운"""
    
    def __init__(self, parent_view):
        self.parent_view = parent_view
        
        # 옵션 생성
        options = []
        for i, tag in enumerate(parent_view.tags):
            emoji = "⭐" if tag['is_primary'] else "💫"
            
            # 간단한 랭크 정보
            if tag['rank_info'] and tag['rank_info'].get('ratings'):
                from utils.overwatch_api import OverwatchAPI
                highest_rank = OverwatchAPI.get_highest_rank(tag['rank_info'])
                description = f"{tag['account_type']} • {highest_rank or '미배치'}"
            else:
                description = f"{tag['account_type']} • 랭크정보 없음"
            
            options.append(discord.SelectOption(
                label=tag['battle_tag'],
                value=str(i),
                description=description[:100],
                emoji=emoji,
                default=(i == 0)  # 첫 번째 항목 기본 선택
            ))
        
        super().__init__(
            placeholder="📋 배틀태그를 선택하여 상세정보 확인",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """선택 시 상세보기 표시"""
        selected_index = int(self.values[0])
        tag = self.parent_view.tags[selected_index]
        
        # 상세 임베드 생성
        embed = discord.Embed(
            title=f"🎮 {tag['battle_tag']}",
            description=f"{'⭐ 주계정' if tag['is_primary'] else '💫 부계정'}",
            color=0x00ff88 if tag['is_primary'] else 0x0099ff,
            timestamp=datetime.now()
        )
        
        # 복사 가능한 배틀태그
        embed.add_field(
            name="📋 배틀태그 (복사용)",
            value=f"```{tag['battle_tag']}```",
            inline=False
        )
        
        # 랭크 정보
        if tag['rank_info'] and tag['rank_info'].get('ratings'):
            rank_display = tag['rank_display']
            embed.add_field(
                name="🏆 오버워치 랭크",
                value=rank_display.replace("**경쟁전 랭크**:\n", ""),
                inline=False
            )
        else:
            embed.add_field(
                name="🏆 오버워치 랭크",
                value="경쟁전 미배치 또는 프로필 비공개",
                inline=False
            )
        
        # 등록 시간
        if tag.get('created_at'):
            created_time = datetime.fromisoformat(tag['created_at'])
            embed.add_field(
                name="📅 등록 일시",
                value=f"<t:{int(created_time.timestamp())}:R>",
                inline=True
            )
        
        embed.set_thumbnail(url=self.parent_view.target_user.display_avatar.url)
        embed.set_footer(text="위 코드 블록의 배틀태그를 드래그하여 복사할 수 있습니다")
        
        # 상세보기 View (뒤로가기 + 개별 새로고침)
        detail_view = BattleTagDetailView(
            self.parent_view.bot,
            self.parent_view.guild_id,
            self.parent_view.user_id,
            self.parent_view.tags,
            self.parent_view.target_user,
            self.parent_view.requester,
            selected_index
        )
        
        await interaction.response.edit_message(embed=embed, view=detail_view)

class BattleTagDetailView(discord.ui.View):
    """배틀태그 상세보기 View"""
    
    def __init__(self, bot, guild_id: str, user_id: str, tags: List[Dict],
                 target_user: discord.Member, requester: discord.Member, selected_index: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.tags = tags
        self.target_user = target_user
        self.requester = requester
        self.selected_index = selected_index
    
    @discord.ui.button(label="뒤로가기", style=discord.ButtonStyle.secondary, emoji="◀️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """목록으로 돌아가기"""
        # 메인 View로 복귀
        main_view = BattleTagListView(
            self.bot, self.guild_id, self.user_id, self.tags,
            self.target_user, self.requester
        )
        
        embed = main_view.create_main_embed()
        await interaction.response.edit_message(embed=embed, view=main_view)
    
    @discord.ui.button(label="이 계정 새로고침", style=discord.ButtonStyle.success, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """현재 배틀태그만 새로고침"""
        await interaction.response.defer()
        
        tag = self.tags[self.selected_index]
        battle_tag = tag['battle_tag']
        
        # API 호출
        rank_info = await self.bot.db_manager.refresh_battle_tag_rank(
            self.guild_id, self.user_id, battle_tag
        )
        
        if rank_info:
            # 태그 목록 재조회
            self.tags = await self.bot.db_manager.get_user_battle_tags_with_rank(
                self.guild_id, self.user_id
            )
            updated_tag = self.tags[self.selected_index]
            
            # 임베드 재생성
            embed = discord.Embed(
                title=f"🎮 {updated_tag['battle_tag']}",
                description=f"{'⭐ 주계정' if updated_tag['is_primary'] else '💫 부계정'}\n\n✅ 랭크 정보 갱신 완료",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📋 배틀태그",
                value=f"```{updated_tag['battle_tag']}```",
                inline=False
            )
            
            if updated_tag['rank_info'] and updated_tag['rank_info'].get('ratings'):
                rank_display = updated_tag['rank_display']
                embed.add_field(
                    name="🏆 오버워치 랭크",
                    value=rank_display.replace("**경쟁전 랭크**:\n", ""),
                    inline=False
                )
            
            embed.set_thumbnail(url=self.target_user.display_avatar.url)
            embed.set_footer(text="랭크 정보가 업데이트되었습니다")
            
            # View 재생성
            new_view = BattleTagDetailView(
                self.bot, self.guild_id, self.user_id, self.tags,
                self.target_user, self.requester, self.selected_index
            )
            
            await interaction.edit_original_response(embed=embed, view=new_view)
        else:
            # 실패 메시지
            await interaction.followup.send(
                f"⚠️ **{battle_tag}** 랭크 정보 갱신 실패 (비공개 또는 없는 계정)",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(BattleTagCommands(bot))