import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict
import re
import math

class TeamInfoCommands(commands.Cog):
    """음성 채널 팀 정보 조회 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="팀정보", description="음성 채널에 있는 팀원들의 배틀태그와 티어 정보를 표시합니다")
    @app_commands.describe(채널="정보를 확인할 음성 채널 (생략 시 본인이 속한 채널)")
    async def team_info(
        self,
        interaction: discord.Interaction,
        채널: Optional[str] = None
    ):
        await interaction.response.defer()
        
        try:
            # 1. 음성 채널 찾기
            voice_channel = await self._find_voice_channel(interaction, 채널)
            
            if not voice_channel:
                await interaction.followup.send(
                    "❌ 음성 채널을 찾을 수 없습니다.\n"
                    "- 드롭다운에서 채널을 선택해주세요.\n"
                    "- 또는 음성 채널에 먼저 참여해주세요.",
                    ephemeral=True
                )
                return
            
            # 2. 음성 채널 멤버 확인
            members = [m for m in voice_channel.members if not m.bot]
            
            if not members:
                await interaction.followup.send(
                    f"❌ `{voice_channel.name}` 채널에 유저가 없습니다.",
                    ephemeral=True
                )
                return
            
            # 3. 각 멤버의 정보 수집
            guild_id = str(interaction.guild_id)
            members_info = []
            
            for member in members:
                user_id = str(member.id)
                
                # 배틀태그 조회
                battle_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
                
                # registered_users에서 티어 정보 조회
                tier_info = await self._get_user_tier(guild_id, user_id)
                
                members_info.append({
                    'member': member,
                    'battle_tags': battle_tags,
                    'tier': tier_info
                })
            
            # 4. 평균 티어 계산
            avg_tier = self._calculate_average_tier(members_info)
            
            # 5. 페이징 View 생성 및 전송
            view = TeamInfoPaginationView(voice_channel, members_info, avg_tier, self.bot)
            embed = view.create_embed()
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ 팀정보 명령어 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 팀 정보를 불러오는 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    @team_info.autocomplete('채널')
    async def channel_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """음성 채널 자동완성"""
        try:
            voice_channels = interaction.guild.voice_channels
            
            # 검색어로 필터링
            matching = []
            for channel in voice_channels:
                if current.lower() in channel.name.lower() or current == "":
                    # 채널에 있는 인원 수 표시
                    member_count = len([m for m in channel.members if not m.bot])
                    display_name = f"{channel.name} ({member_count}명)"
                    
                    matching.append(
                        app_commands.Choice(
                            name=display_name[:100],
                            value=channel.name
                        )
                    )
            
            return matching[:25]
            
        except Exception as e:
            print(f"❌ 채널 자동완성 오류: {e}")
            return []
    
    async def _find_voice_channel(
        self, 
        interaction: discord.Interaction, 
        channel_name: Optional[str]
    ) -> Optional[discord.VoiceChannel]:
        """음성 채널 찾기"""
        
        # 채널명이 주어진 경우
        if channel_name:
            for channel in interaction.guild.voice_channels:
                if channel.name == channel_name:
                    return channel
            return None
        
        # 채널명이 없는 경우 - 사용자가 속한 채널 찾기
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel
        
        return None
    
    async def _get_user_tier(self, guild_id: str, user_id: str) -> Optional[str]:
        """registered_users에서 유저의 현재 시즌 티어 조회"""
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT current_season_tier FROM registered_users
                    WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                ''', (guild_id, user_id)) as cursor:
                    row = await cursor.fetchone()
                    if row and row[0]:
                        return row[0]
            
            return None
        except Exception as e:
            print(f"❌ 티어 조회 실패: {e}")
            return None
    
    def _parse_tier(self, tier_str: Optional[str]) -> Optional[Dict]:
        """
        티어 문자열을 파싱하여 딕셔너리 반환
        예: "플래티넘 2" -> {'tier': 'Platinum', 'division': 2, 'score': 22}
        """
        if not tier_str:
            return None
        
        tier_str = tier_str.strip()
        
        # 티어 매핑 (한글 -> 영문)
        tier_map = {
            '브론즈': ('Bronze', 1),
            '실버': ('Silver', 2),
            '골드': ('Gold', 3),
            '플래티넘': ('Platinum', 4),
            '플레티넘': ('Platinum', 4),
            '플레': ('Platinum', 4),
            '다이아': ('Diamond', 5),
            '다이아몬드': ('Diamond', 5),
            '마스터': ('Master', 6),
            '그랜드마스터': ('Grandmaster', 7),
            '그마': ('Grandmaster', 7),
            '챌린저': ('Champion', 8),
            '챔피언': ('Champion', 8)
        }
        
        # 티어 이름 찾기
        tier_name = None
        tier_level = 0
        for korean, (english, level) in tier_map.items():
            if korean in tier_str:
                tier_name = english
                tier_level = level
                break
        
        if not tier_name:
            return None
        
        # 디비전 찾기 (1-5)
        division = 3  # 기본값
        match = re.search(r'(\d+)', tier_str)
        if match:
            division = int(match.group(1))
            if division < 1:
                division = 1
            elif division > 5:
                division = 5
        
        # 점수 계산 (디비전이 낮을수록 높은 점수)
        # 각 티어는 5점 범위, 디비전 1이 가장 높음
        score = tier_level * 5 + (6 - division)
        
        return {
            'tier': tier_name,
            'division': division,
            'score': score
        }
    
    def _calculate_average_tier(self, members_info: List[Dict]) -> str:
        """평균 티어 계산 (본계정 기준)"""
        tier_scores = []
        
        for info in members_info:
            tier_str = info['tier']
            if not tier_str:
                continue
            
            parsed = self._parse_tier(tier_str)
            if parsed:
                tier_scores.append(parsed['score'])
        
        if not tier_scores:
            return "티어 정보 없음"
        
        # 평균 점수 계산
        avg_score = sum(tier_scores) / len(tier_scores)
        
        # 점수를 티어로 역변환
        tier_level = int(avg_score // 5)
        remainder = avg_score % 5
        division = 6 - int(round(remainder))
        
        # 디비전 보정
        if division < 1:
            division = 1
        elif division > 5:
            division = 5
        
        # 티어 이름 매핑
        tier_names = {
            1: '브론즈',
            2: '실버',
            3: '골드',
            4: '플레',
            5: '다이아',
            6: '마스터',
            7: '그마',
            8: '챌린저'
        }
        
        tier_name = tier_names.get(tier_level, '언랭')
        
        # 디버그 로그
        print(f"[DEBUG] 평균 티어 계산: avg_score={avg_score:.2f}, tier_level={tier_level}, division={division}")
        
        return f"{tier_name} {division}"
    
    def _format_tier_display(self, tier_str: Optional[str]) -> str:
        """티어를 짧은 형식으로 변환"""
        if not tier_str:
            return ""
        
        tier_str = tier_str.strip()
        
        # 짧은 형식으로 변환
        tier_str = tier_str.replace('플래티넘', '플레')
        tier_str = tier_str.replace('플레티넘', '플레')
        tier_str = tier_str.replace('다이아몬드', '다이아')
        tier_str = tier_str.replace('그랜드마스터', '그마')
        tier_str = tier_str.replace('챔피언', '챌린저')
        
        return tier_str


class TeamInfoPaginationView(discord.ui.View):
    """팀 정보 페이징 View"""
    
    def __init__(self, voice_channel: discord.VoiceChannel, members_info: List[Dict], avg_tier: str, bot):
        super().__init__(timeout=600)  # 10분으로 연장
        self.voice_channel = voice_channel
        self.members_info = members_info
        self.avg_tier = avg_tier
        self.bot = bot
        self.current_page = 0
        self.members_per_page = 5
        self.total_pages = math.ceil(len(members_info) / self.members_per_page)
        
        # 버튼 업데이트
        self.update_buttons()
    
    def update_buttons(self):
        """버튼 상태 업데이트"""
        # 이전/다음 버튼 활성화/비활성화
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
    
    def create_embed(self) -> discord.Embed:
        """현재 페이지의 임베드 생성"""
        
        # 페이지 정보
        page_info = f" ({self.current_page + 1}/{self.total_pages})" if self.total_pages > 1 else ""
        
        embed = discord.Embed(
            title=f"🎮 {self.voice_channel.name} 팀 정보{page_info}",
            color=0x00D9FF,
            description=f"━━━━━━━━━━━━━━━━━━\n"
                       f"**총 인원:** {len(self.members_info)}명 | **평균 티어:** {self.avg_tier}"
        )
        
        # 현재 페이지의 멤버만 표시
        start_idx = self.current_page * self.members_per_page
        end_idx = min(start_idx + self.members_per_page, len(self.members_info))
        page_members = self.members_info[start_idx:end_idx]
        
        # 각 멤버 정보 추가
        member_lines = []
        
        for info in page_members:
            member = info['member']
            battle_tags = info['battle_tags']
            tier = info['tier']
            
            # 티어 포맷팅
            tier_display = ""
            if tier:
                cog = TeamInfoCommands(self.bot)
                tier_display = f" ({cog._format_tier_display(tier)})"
            
            # 닉네임 + 티어
            member_lines.append(f"\n👤 **{member.display_name}**{tier_display}")
            
            if not battle_tags:
                member_lines.append("   ⚠️ 등록된 배틀태그 없음")
            else:
                # 최대 4개까지만 표시
                max_display = 4
                displayed_tags = battle_tags[:max_display]
                remaining_count = len(battle_tags) - max_display
                
                for tag_info in displayed_tags:
                    battle_tag = tag_info['battle_tag']
                    member_lines.append(f"```{battle_tag}```")
                
                # 4개 초과 시 안내 문구
                if remaining_count > 0:
                    member_lines.append(f"   💬 외 {remaining_count}개 더 있음 (전체 보기: `/배틀태그목록`)")
        
        # 멤버 정보 필드에 추가
        embed.add_field(
            name="\u200b",
            value="".join(member_lines),
            inline=False
        )
        
        embed.set_footer(text="💡 각 배틀태그 옆 복사 버튼을 클릭하세요")
        
        return embed
    
    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="배틀태그 추가", style=discord.ButtonStyle.success, emoji="➕", custom_id="add_tag", row=0)
    async def add_battle_tag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """배틀태그 추가 버튼"""
        # 등록된 유저인지 확인
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # DB에서 등록 여부 확인
        import aiosqlite
        async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
            async with db.execute('''
                SELECT user_id FROM registered_users
                WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
            ''', (guild_id, user_id)) as cursor:
                is_registered = await cursor.fetchone() is not None
        
        if not is_registered:
            await interaction.response.send_message(
                "❌ 등록되지 않은 유저입니다. `/유저신청` 명령어로 먼저 가입 신청을 해주세요.",
                ephemeral=True
            )
            return
        
        # 계정 타입 선택 View 표시
        view = AccountTypeSelectView(self, self.bot)
        await interaction.response.send_message(
            "**계정 타입을 선택해주세요:**",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for item in self.children:
            item.disabled = True


class AccountTypeSelectView(discord.ui.View):
    """계정 타입 선택 View"""
    
    def __init__(self, parent_view: TeamInfoPaginationView, bot):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bot = bot
    
    @discord.ui.button(label="본계정", style=discord.ButtonStyle.primary, emoji="⭐")
    async def main_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """본계정 선택"""
        modal = AddBattleTagModal(self.parent_view, self.bot, "main")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="부계정", style=discord.ButtonStyle.secondary, emoji="💫")
    async def sub_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """부계정 선택"""
        modal = AddBattleTagModal(self.parent_view, self.bot, "sub")
        await interaction.response.send_modal(modal)


class AddBattleTagModal(discord.ui.Modal, title="배틀태그 추가"):
    """배틀태그 추가 Modal"""
    
    battle_tag_input = discord.ui.TextInput(
        label="배틀태그",
        placeholder="예: backyerin#3538",
        required=True,
        min_length=3,
        max_length=50
    )
    
    def __init__(self, parent_view: TeamInfoPaginationView, bot, account_type: str):
        super().__init__()
        self.parent_view = parent_view
        self.bot = bot
        self.account_type = account_type
        
        # 타이틀 변경
        if account_type == "main":
            self.title = "본계정 배틀태그 추가"
        else:
            self.title = "부계정 배틀태그 추가"
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            battle_tag = self.battle_tag_input.value.strip()
            
            # 배틀태그 형식 검증
            from utils.helpers import validate_battle_tag_format
            
            if not validate_battle_tag_format(battle_tag):
                await interaction.followup.send(
                    "❌ 올바르지 않은 배틀태그 형식입니다.\n"
                    "**형식**: `이름#1234` (예: backyerin#3538)",
                    ephemeral=True
                )
                return
            
            # 배틀태그 추가 + API 호출
            success, rank_info = await self.bot.db_manager.add_battle_tag_with_api(
                guild_id, user_id, battle_tag, self.account_type
            )
            
            if not success:
                await interaction.followup.send(
                    f"❌ 배틀태그 추가 실패\n"
                    f"• 이미 등록된 배틀태그일 수 있습니다.\n"
                    f"• `/배틀태그목록`으로 확인해보세요.",
                    ephemeral=True
                )
                return
            
            # 성공 메시지
            account_type_text = "본계정" if self.account_type == "main" else "부계정"
            success_msg = f"✅ **{battle_tag}** ({account_type_text}) 추가 완료!"
            if rank_info:
                success_msg += f"\n🎮 랭크 정보도 자동으로 저장되었습니다."
            
            await interaction.followup.send(success_msg, ephemeral=True)
            
            # 팀 정보 새로고침
            await self.refresh_team_info(interaction)
            
        except Exception as e:
            print(f"❌ 배틀태그 추가 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 배틀태그 추가 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def refresh_team_info(self, interaction: discord.Interaction):
        """팀 정보 임베드 새로고침"""
        try:
            # 음성 채널의 모든 멤버 정보 다시 조회
            voice_channel = self.parent_view.voice_channel
            members = [m for m in voice_channel.members if not m.bot]
            
            guild_id = str(interaction.guild_id)
            members_info = []
            
            for member in members:
                user_id = str(member.id)
                
                # 배틀태그 조회
                battle_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
                
                # registered_users에서 티어 정보 조회
                import aiosqlite
                async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                    async with db.execute('''
                        SELECT current_season_tier FROM registered_users
                        WHERE guild_id = ? AND user_id = ? AND is_active = TRUE
                    ''', (guild_id, user_id)) as cursor:
                        row = await cursor.fetchone()
                        tier_info = row[0] if row and row[0] else None
                
                members_info.append({
                    'member': member,
                    'battle_tags': battle_tags,
                    'tier': tier_info
                })
            
            # 평균 티어 재계산
            cog = TeamInfoCommands(self.bot)
            avg_tier = cog._calculate_average_tier(members_info)
            
            # View 업데이트
            self.parent_view.members_info = members_info
            self.parent_view.avg_tier = avg_tier
            
            # 임베드 재생성 및 업데이트
            embed = self.parent_view.create_embed()
            
            # 원본 메시지 찾기 및 수정
            # interaction.message는 Modal이 열린 버튼의 메시지
            async for msg in interaction.channel.history(limit=20):
                if msg.author == self.bot.user and len(msg.embeds) > 0:
                    embed_title = msg.embeds[0].title
                    if self.parent_view.voice_channel.name in embed_title:
                        await msg.edit(embed=embed, view=self.parent_view)
                        break
            
        except Exception as e:
            print(f"❌ 팀 정보 새로고침 오류: {e}")
            import traceback
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(TeamInfoCommands(bot))