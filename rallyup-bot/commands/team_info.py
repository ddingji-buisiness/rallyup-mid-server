import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict
import re
import math
import asyncio
from datetime import datetime

class TeamInfoCommands(commands.Cog):
    """음성 채널 팀 정보 조회 + 자동 모니터링"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # 음성 모니터링 관련
        self.channel_messages: Dict[str, Dict[str, int]] = {}  # {guild_id: {voice_channel_id: message_id}}
        self.update_tasks: Dict[str, Dict[str, asyncio.Task]] = {}  # Debouncing 태스크
        self.active_guilds: set = set()  # 모니터링 활성화된 서버
    
    # ==================== 기존 /팀정보 명령어 ====================
    
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
            
            # 3. 멤버 정보 수집 (공통 메서드)
            guild_id = str(interaction.guild_id)
            members_info = await self._collect_members_info(guild_id, members)
            
            # 4. 평균 티어 계산
            avg_tier = self._calculate_average_tier(members_info)
            
            # 5. 페이징 View 생성 및 전송
            view = TeamInfoPaginationView(voice_channel, members_info, avg_tier, self.bot, self)
            embed = self._create_team_embed(voice_channel, members_info, avg_tier, 0, is_manual=True)
            
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
            
            matching = []
            for channel in voice_channels:
                if current.lower() in channel.name.lower() or current == "":
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
    
    # ==================== 음성 모니터링 이벤트 ====================
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ):
        """음성 채널 입장/퇴장 자동 감지"""
        
        if member.bot:
            return
        
        guild_id = str(member.guild.id)
        
        # 모니터링 활성화 확인
        if guild_id not in self.active_guilds:
            return
        
        # before 채널 업데이트
        if before.channel:
            await self._schedule_update(before.channel)
        
        # after 채널 업데이트
        if after.channel:
            await self._schedule_update(after.channel)
    
    async def _schedule_update(self, voice_channel: discord.VoiceChannel, delay: float = 2.0):
        """업데이트 예약 (Debouncing)"""
        guild_id = str(voice_channel.guild.id)
        channel_id = str(voice_channel.id)
        
        # 기존 태스크 취소
        if guild_id in self.update_tasks and channel_id in self.update_tasks[guild_id]:
            self.update_tasks[guild_id][channel_id].cancel()
        
        # 새 태스크 생성
        if guild_id not in self.update_tasks:
            self.update_tasks[guild_id] = {}
        
        self.update_tasks[guild_id][channel_id] = asyncio.create_task(
            self._delayed_update(voice_channel, delay)
        )
    
    async def _delayed_update(self, voice_channel: discord.VoiceChannel, delay: float):
        """지연된 업데이트 실행"""
        try:
            await asyncio.sleep(delay)
            await self._auto_update_team_info(voice_channel)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ 자동 팀정보 업데이트 오류: {e}")
    
    async def _auto_update_team_info(self, voice_channel: discord.VoiceChannel):
        """팀정보 자동 업데이트 (음성 모니터링용)"""
        try:
            guild_id = str(voice_channel.guild.id)
            channel_id = str(voice_channel.id)
            
            # 1. 멤버 확인
            members = [m for m in voice_channel.members if not m.bot]
            
            # 2. 텍스트 채널 찾기 (같은 이름 + 권한 체크)
            text_channel = await self._find_text_channel(voice_channel)
            if not text_channel:
                # 로그: 채널 없음 또는 권한 없음
                print(f"ℹ️ 팀정보 발송 불가: {voice_channel.name} (같은 이름의 텍스트 채널 없음 또는 권한 부족)")
                return
            
            # 3. 멤버 정보 수집
            members_info = await self._collect_members_info(guild_id, members)
            avg_tier = self._calculate_average_tier(members_info)
            
            # 4. 임베드 생성
            embed = self._create_team_embed(voice_channel, members_info, avg_tier, 0, is_manual=False)
            
            # 5. 메시지 업데이트 또는 생성
            if guild_id in self.channel_messages and channel_id in self.channel_messages[guild_id]:
                # 기존 메시지 수정 시도
                message_id = self.channel_messages[guild_id][channel_id]
                try:
                    message = await text_channel.fetch_message(message_id)
                    
                    if not members:
                        # 멤버 없으면 삭제
                        await message.delete()
                        del self.channel_messages[guild_id][channel_id]
                        return
                    
                    view = AutoTeamInfoView(voice_channel, members_info, avg_tier, self.bot, self)
                    await message.edit(embed=embed, view=view)
                    
                except discord.NotFound:
                    if members:
                        view = AutoTeamInfoView(voice_channel, members_info, avg_tier, self.bot, self)
                        new_message = await text_channel.send(embed=embed, view=view)
                        self.channel_messages[guild_id][channel_id] = new_message.id
                    else:
                        del self.channel_messages[guild_id][channel_id]
            else:
                # 새 메시지 생성
                if members:
                    view = AutoTeamInfoView(voice_channel, members_info, avg_tier, self.bot, self)
                    new_message = await text_channel.send(embed=embed, view=view)
                    
                    if guild_id not in self.channel_messages:
                        self.channel_messages[guild_id] = {}
                    self.channel_messages[guild_id][channel_id] = new_message.id
        
        except discord.Forbidden:
            # 권한 문제 - 이 경우는 발생하지 않아야 함 (_find_text_channel에서 미리 체크)
            print(f"❌ 예상치 못한 권한 오류: {voice_channel.name}")
        except Exception as e:
            print(f"❌ 자동 팀정보 업데이트 실패: {voice_channel.name} - {e}")
            import traceback
            traceback.print_exc()
    
    # ==================== 음성 모니터링 설정 명령어 ====================
    
    @app_commands.command(name="음성모니터", description="[관리자] 음성 채널 자동 팀정보 모니터링 설정")
    @app_commands.describe(활성화="모니터링 활성화 여부")
    @app_commands.default_permissions(manage_guild=True)
    async def voice_monitor_setup(
        self,
        interaction: discord.Interaction,
        활성화: bool
    ):
        """음성 모니터링 설정"""
        if not await self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            if 활성화:
                self.active_guilds.add(guild_id)
                status = "활성화"
                color = 0x00ff88
            else:
                self.active_guilds.discard(guild_id)
                status = "비활성화"
                color = 0x666666
            
            embed = discord.Embed(
                title=f"{'✅' if 활성화 else '⬜'} 음성 모니터링 {status}",
                description=f"서버 전체 음성 채널 자동 팀정보가 **{status}**되었습니다",
                color=color
            )
            
            embed.add_field(
                name="📋 동작 방식",
                value="• 유저가 음성 채널 입장 시 자동으로 팀정보 메시지 발송\n"
                      "• 유저 입장/퇴장 시 실시간 업데이트 (2초 딜레이)\n"
                      "• 같은 이름의 텍스트 채널에 자동 발송\n"
                      "• 모든 유저 퇴장 시 메시지 자동 삭제",
                inline=False
            )
            
            if 활성화:
                embed.add_field(
                    name="💡 권장 채널 구조",
                    value="```\n"
                          "📁 스크림\n"
                          "  ├─ 🔊 스크림-1 (음성)\n"
                          "  ├─ 💬 스크림-1 (텍스트) ← 여기에 발송\n"
                          "  ├─ 🔊 스크림-2 (음성)\n"
                          "  └─ 💬 스크림-2 (텍스트)\n"
                          "```",
                    inline=False
                )
            
            embed.set_footer(text="RallyUp Bot | 음성 채널 모니터링")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 설정 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    @app_commands.command(name="음성진단", description="[관리자] 음성 채널 모니터링 상태 및 권한 진단")
    @app_commands.default_permissions(manage_guild=True)
    async def voice_diagnose(self, interaction: discord.Interaction):
        """음성 모니터링 진단"""
        if not await self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            guild_id = str(guild.id)
            bot_member = guild.get_member(self.bot.user.id)
            
            embed = discord.Embed(
                title="🔍 음성 모니터링 진단 결과",
                color=0x0099ff,
                timestamp=datetime.now()
            )
            
            # 1. 모니터링 활성화 상태 (DB에서 확인)
            is_active = await self.bot.db_manager.is_voice_monitor_enabled(guild_id)
            embed.add_field(
                name="📊 모니터링 상태",
                value=f"{'✅ 활성화' if is_active else '⬜ 비활성화'}\n"
                      f"명령어: `/음성모니터 활성화:{'False' if is_active else 'True'}`",
                inline=False
            )
            
            # 2. 음성 채널 목록 및 권한 체크
            voice_channels = guild.voice_channels
            channel_status = []
            
            for vc in voice_channels[:10]:  # 최대 10개
                # 텍스트 채널 찾기
                text_channel = None
                for tc in guild.text_channels:
                    if tc.name.lower() == vc.name.lower():
                        text_channel = tc
                        break
                
                if text_channel:
                    # 권한 체크
                    perms = text_channel.permissions_for(bot_member)
                    has_send = perms.send_messages
                    has_embed = perms.embed_links
                    
                    if has_send and has_embed:
                        status = "✅"
                        detail = "정상"
                    elif has_send:
                        status = "⚠️"
                        detail = "임베드 권한 없음"
                    else:
                        status = "❌"
                        detail = "메시지 전송 권한 없음"
                else:
                    status = "⬜"
                    detail = "텍스트 채널 없음"
                
                # 인원 수
                member_count = len([m for m in vc.members if not m.bot])
                
                channel_status.append(
                    f"{status} **{vc.name}** ({member_count}명)\n"
                    f"   └ {detail}"
                )
            
            if len(voice_channels) > 10:
                channel_status.append(f"\n... 외 {len(voice_channels) - 10}개 채널")
            
            embed.add_field(
                name="🔊 음성 채널 상태",
                value="\n".join(channel_status) if channel_status else "음성 채널 없음",
                inline=False
            )
            
            # 3. 봇 권한 확인
            bot_perms = bot_member.guild_permissions
            required_perms = {
                "메시지 보내기": bot_perms.send_messages,
                "임베드 링크": bot_perms.embed_links,
                "메시지 기록 보기": bot_perms.read_message_history,
                "채널 보기": bot_perms.view_channel,
            }
            
            perm_status = []
            for perm_name, has_perm in required_perms.items():
                perm_status.append(f"{'✅' if has_perm else '❌'} {perm_name}")
            
            embed.add_field(
                name="🔐 봇 기본 권한",
                value="\n".join(perm_status),
                inline=False
            )
            
            # 4. 캐시된 메시지 개수
            cached_count = len(self.channel_messages.get(guild_id, {}))
            embed.add_field(
                name="📝 활성 모니터링 메시지",
                value=f"{cached_count}개 채널에서 활성 중",
                inline=False
            )
            
            embed.set_footer(text="문제가 있는 채널은 권한을 확인해주세요")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 진단 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 진단 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    @app_commands.command(name="음성채널자동생성", description="[관리자] 음성 채널에 대응하는 텍스트 채널 자동 생성")
    @app_commands.describe(
        카테고리="텍스트 채널을 생성할 카테고리 (선택사항)",
        미리보기="실제 생성하지 않고 미리보기만"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def auto_create_text_channels(
        self,
        interaction: discord.Interaction,
        카테고리: Optional[str] = None,
        미리보기: bool = True
    ):
        """음성 채널에 대응하는 텍스트 채널 자동 생성"""
        if not await self._is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            
            # 카테고리 필터링
            target_category = None
            if 카테고리:
                for cat in guild.categories:
                    if cat.name.lower() == 카테고리.lower():
                        target_category = cat
                        break
                
                if not target_category:
                    await interaction.followup.send(
                        f"❌ '{카테고리}' 카테고리를 찾을 수 없습니다.",
                        ephemeral=True
                    )
                    return
            
            # 생성할 채널 목록 수집
            channels_to_create = []
            
            voice_channels = guild.voice_channels
            if target_category:
                voice_channels = [vc for vc in voice_channels if vc.category == target_category]
            
            for vc in voice_channels:
                # 같은 이름의 텍스트 채널이 이미 있는지 확인
                text_exists = False
                for tc in guild.text_channels:
                    if tc.name.lower() == vc.name.lower():
                        text_exists = True
                        break
                
                if not text_exists:
                    channels_to_create.append(vc)
            
            if not channels_to_create:
                await interaction.followup.send(
                    "✅ 모든 음성 채널에 이미 대응하는 텍스트 채널이 있습니다!",
                    ephemeral=True
                )
                return
            
            # 미리보기 또는 실제 생성
            if 미리보기:
                # 미리보기 임베드
                embed = discord.Embed(
                    title="📋 생성 예정 텍스트 채널 목록",
                    description=f"총 **{len(channels_to_create)}개** 채널이 생성됩니다",
                    color=0x0099ff
                )
                
                preview_lines = []
                for vc in channels_to_create[:15]:  # 최대 15개
                    category_name = vc.category.name if vc.category else "카테고리 없음"
                    preview_lines.append(
                        f"💬 **{vc.name}**\n"
                        f"   └ 위치: {category_name}"
                    )
                
                if len(channels_to_create) > 15:
                    preview_lines.append(f"\n... 외 {len(channels_to_create) - 15}개")
                
                embed.add_field(
                    name="\u200b",
                    value="\n".join(preview_lines),
                    inline=False
                )
                
                embed.add_field(
                    name="⚠️ 다음 명령어로 실제 생성",
                    value=f"`/음성채널자동생성 미리보기:False`" + 
                          (f" `카테고리:{카테고리}`" if 카테고리 else ""),
                    inline=False
                )
                
                embed.set_footer(text="생성된 채널은 같은 카테고리에 배치됩니다")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                # 실제 생성
                created_count = 0
                failed_channels = []
                
                for vc in channels_to_create:
                    try:
                        # 같은 카테고리에 텍스트 채널 생성
                        await guild.create_text_channel(
                            name=vc.name,
                            category=vc.category,
                            reason=f"음성 채널 '{vc.name}'에 대응하는 텍스트 채널 자동 생성"
                        )
                        created_count += 1
                    except discord.Forbidden:
                        failed_channels.append(f"{vc.name} (권한 부족)")
                    except discord.HTTPException as e:
                        failed_channels.append(f"{vc.name} ({str(e)})")
                
                # 결과 임베드
                embed = discord.Embed(
                    title="✅ 텍스트 채널 생성 완료",
                    description=f"**{created_count}개** 채널이 생성되었습니다",
                    color=0x00ff88,
                    timestamp=datetime.now()
                )
                
                if failed_channels:
                    embed.add_field(
                        name="⚠️ 생성 실패",
                        value="\n".join(failed_channels[:10]),
                        inline=False
                    )
                
                embed.add_field(
                    name="💡 다음 단계",
                    value="1. `/음성진단` 명령어로 상태 확인\n"
                          "2. 봇 권한 확인 (메시지 보내기, 임베드)\n"
                          "3. 음성 채널 입장 테스트",
                    inline=False
                )
                
                embed.set_footer(text="RallyUp Bot | 자동 채널 생성")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 채널 생성 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 채널 생성 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    @auto_create_text_channels.autocomplete('카테고리')
    async def category_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """카테고리 자동완성"""
        try:
            categories = interaction.guild.categories
            
            matching = []
            for category in categories:
                if current.lower() in category.name.lower() or current == "":
                    # 카테고리 내 음성 채널 개수
                    voice_count = len([c for c in category.voice_channels])
                    
                    matching.append(
                        app_commands.Choice(
                            name=f"{category.name} ({voice_count}개 음성 채널)",
                            value=category.name
                        )
                    )
            
            return matching[:25]
            
        except Exception as e:
            print(f"❌ 카테고리 자동완성 오류: {e}")
            return []
    
    # ==================== 공통 유틸리티 메서드 ====================
    
    async def _find_voice_channel(
        self, 
        interaction: discord.Interaction, 
        channel_name: Optional[str]
    ) -> Optional[discord.VoiceChannel]:
        """음성 채널 찾기"""
        if channel_name:
            for channel in interaction.guild.voice_channels:
                if channel.name == channel_name:
                    return channel
            return None
        
        if interaction.user.voice and interaction.user.voice.channel:
            return interaction.user.voice.channel
        
        return None
    
    async def _find_text_channel(self, voice_channel: discord.VoiceChannel) -> Optional[discord.TextChannel]:
        """
        음성 채널에 대응하는 텍스트 채널 찾기
        ⚠️ 보안: 같은 이름의 채널만 허용, 없으면 None 반환
        """
        guild = voice_channel.guild
        bot_member = guild.get_member(self.bot.user.id)
        
        # 같은 이름의 텍스트 채널만 찾기
        for channel in guild.text_channels:
            if channel.name.lower() == voice_channel.name.lower():
                # 권한 체크
                perms = channel.permissions_for(bot_member)
                if perms.send_messages and perms.embed_links:
                    return channel
                else:
                    # 권한 없음 로그
                    print(f"⚠️ 채널 권한 없음: {channel.name} (메시지 전송/임베드 권한 필요)")
                    return None
        
        # 같은 이름의 채널이 없으면 None 반환 (절대 다른 채널 사용 안 함)
        return None
    
    async def _collect_members_info(self, guild_id: str, members: List[discord.Member]) -> List[Dict]:
        """멤버 정보 수집 (공통 메서드)"""
        members_info = []
        
        for member in members:
            user_id = str(member.id)
            battle_tags = await self.bot.db_manager.get_user_battle_tags(guild_id, user_id)
            tier_info = await self._get_user_tier(guild_id, user_id)
            
            members_info.append({
                'member': member,
                'battle_tags': battle_tags,
                'tier': tier_info
            })
        
        return members_info
    
    async def _get_user_tier(self, guild_id: str, user_id: str) -> Optional[str]:
        """유저 티어 조회"""
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
    
    def _create_team_embed(
        self, 
        voice_channel: discord.VoiceChannel, 
        members_info: List[Dict], 
        avg_tier: str,
        page: int = 0,
        members_per_page: int = 5,
        is_manual: bool = True
    ) -> discord.Embed:
        """팀정보 임베드 생성 (공통 메서드)"""
        
        total_pages = math.ceil(len(members_info) / members_per_page)
        page_info = f" ({page + 1}/{total_pages})" if total_pages > 1 else ""
        
        embed = discord.Embed(
            title=f"🎮 {voice_channel.name} 팀 정보{page_info}",
            color=0x00D9FF,
            description=f"━━━━━━━━━━━━━━━━━━\n"
                       f"**총 인원:** {len(members_info)}명 | **평균 티어:** {avg_tier}",
            timestamp=datetime.now()
        )
        
        # 페이징
        start_idx = page * members_per_page
        end_idx = min(start_idx + members_per_page, len(members_info))
        page_members = members_info[start_idx:end_idx]
        
        # 멤버 정보 추가
        member_lines = []
        
        for info in page_members:
            member = info['member']
            battle_tags = info['battle_tags']
            tier = info['tier']
            
            tier_display = ""
            if tier:
                tier_display = f" ({self._format_tier_display(tier)})"
            
            member_lines.append(f"\n👤 **{member.display_name}**{tier_display}")
            
            if not battle_tags:
                member_lines.append("   ⚠️ 등록된 배틀태그 없음")
            else:
                # 수동/자동 모두 동일하게 4개 표시
                max_display = 4
                displayed_tags = battle_tags[:max_display]
                remaining_count = len(battle_tags) - max_display
                
                # 수동/자동 모두 동일한 UI (코드블록 사용)
                for tag_info in displayed_tags:
                    battle_tag = tag_info['battle_tag']
                    member_lines.append(f"```{battle_tag}```")
                
                if remaining_count > 0:
                    member_lines.append(f"   💬 외 {remaining_count}개 더 있음 (전체 보기: `/배틀태그목록`)")
        
        embed.add_field(
            name="\u200b",
            value="".join(member_lines) if member_lines else "멤버가 없습니다",
            inline=False
        )
        
        # Footer만 구분
        if is_manual:
            embed.set_footer(text="💡 각 배틀태그 옆 복사 버튼을 클릭하세요")
        else:
            embed.set_footer(text="🔄 자동 업데이트 | 위 코드블록을 드래그하여 복사하세요")
        
        return embed
    
    def _calculate_average_tier(self, members_info: List[Dict]) -> str:
        """평균 티어 계산"""
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
        
        avg_score = sum(tier_scores) / len(tier_scores)
        tier_level = int(avg_score // 5)
        remainder = avg_score % 5
        division = 6 - int(round(remainder))
        
        if division < 1:
            division = 1
        elif division > 5:
            division = 5
        
        tier_names = {
            1: '브론즈', 2: '실버', 3: '골드', 4: '플레',
            5: '다이아', 6: '마스터', 7: '그마', 8: '챌린저'
        }
        
        tier_name = tier_names.get(tier_level, '언랭')
        return f"{tier_name} {division}"
    
    def _parse_tier(self, tier_str: Optional[str]) -> Optional[Dict]:
        """티어 문자열 파싱"""
        if not tier_str:
            return None
        
        tier_str = tier_str.strip()
        
        tier_map = {
            '브론즈': ('Bronze', 1), '실버': ('Silver', 2), '골드': ('Gold', 3),
            '플래티넘': ('Platinum', 4), '플레티넘': ('Platinum', 4), '플레': ('Platinum', 4),
            '다이아': ('Diamond', 5), '다이아몬드': ('Diamond', 5),
            '마스터': ('Master', 6), '그랜드마스터': ('Grandmaster', 7), '그마': ('Grandmaster', 7),
            '챌린저': ('Champion', 8), '챔피언': ('Champion', 8)
        }
        
        tier_name = None
        tier_level = 0
        for korean, (english, level) in tier_map.items():
            if korean in tier_str:
                tier_name = english
                tier_level = level
                break
        
        if not tier_name:
            return None
        
        division = 3
        match = re.search(r'(\d+)', tier_str)
        if match:
            division = int(match.group(1))
            if division < 1:
                division = 1
            elif division > 5:
                division = 5
        
        score = tier_level * 5 + (6 - division)
        
        return {'tier': tier_name, 'division': division, 'score': score}
    
    def _format_tier_display(self, tier_str: Optional[str]) -> str:
        """티어 짧은 형식 변환"""
        if not tier_str:
            return ""
        
        tier_str = tier_str.strip()
        tier_str = tier_str.replace('플래티넘', '플레').replace('플레티넘', '플레')
        tier_str = tier_str.replace('다이아몬드', '다이아')
        tier_str = tier_str.replace('그랜드마스터', '그마')
        tier_str = tier_str.replace('챔피언', '챌린저')
        
        return tier_str
    
    async def _is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)


# ==================== View 클래스 ====================

class TeamInfoPaginationView(discord.ui.View):
    """수동 /팀정보 명령어용 View"""
    
    def __init__(self, voice_channel: discord.VoiceChannel, members_info: List[Dict], avg_tier: str, bot, cog):
        super().__init__(timeout=600)
        self.voice_channel = voice_channel
        self.members_info = members_info
        self.avg_tier = avg_tier
        self.bot = bot
        self.cog = cog
        self.current_page = 0
        self.members_per_page = 5
        self.total_pages = math.ceil(len(members_info) / self.members_per_page)
        
        self.update_buttons()
    
    def update_buttons(self):
        """버튼 상태 업데이트"""
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= self.total_pages - 1)
    
    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=True
            )
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="배틀태그 추가", style=discord.ButtonStyle.success, emoji="➕", custom_id="add_tag", row=0)
    async def add_battle_tag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
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
        
        view = AccountTypeSelectView(self, self.bot)
        await interaction.response.send_message(
            "**계정 타입을 선택해주세요:**",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=True
            )
            await interaction.response.edit_message(embed=embed, view=self)


class AutoTeamInfoView(discord.ui.View):
    """자동 음성 모니터링용 View"""
    
    def __init__(self, voice_channel: discord.VoiceChannel, members_info: List[Dict], avg_tier: str, bot, cog):
        super().__init__(timeout=None)
        self.voice_channel = voice_channel
        self.members_info = members_info
        self.avg_tier = avg_tier
        self.bot = bot
        self.cog = cog
        self.current_page = 0
        self.members_per_page = 5
        self.total_pages = math.ceil(len(members_info) / self.members_per_page)
        
        self.update_buttons()
    
    def update_buttons(self):
        """페이지가 1개면 페이징 버튼 숨김"""
        if self.total_pages <= 1:
            # 페이징 버튼 제거
            items_to_remove = []
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id in ["prev_auto", "next_auto"]:
                    items_to_remove.append(item)
            for item in items_to_remove:
                self.remove_item(item)
        else:
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    if item.custom_id == "prev_auto":
                        item.disabled = (self.current_page == 0)
                    elif item.custom_id == "next_auto":
                        item.disabled = (self.current_page >= self.total_pages - 1)
    
    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev_auto", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=False
            )
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="새로고침", style=discord.ButtonStyle.success, emoji="🔄", custom_id="refresh_auto", row=0)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog._auto_update_team_info(self.voice_channel)
    
    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next_auto", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=False
            )
            await interaction.response.edit_message(embed=embed, view=self)


class AccountTypeSelectView(discord.ui.View):
    """계정 타입 선택 View"""
    
    def __init__(self, parent_view, bot):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bot = bot
    
    @discord.ui.button(label="본계정", style=discord.ButtonStyle.primary, emoji="⭐")
    async def main_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddBattleTagModal(self.parent_view, self.bot, "main")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="부계정", style=discord.ButtonStyle.secondary, emoji="💫")
    async def sub_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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
    
    def __init__(self, parent_view, bot, account_type: str):
        super().__init__()
        self.parent_view = parent_view
        self.bot = bot
        self.account_type = account_type
        
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
            
            from utils.helpers import validate_battle_tag_format
            
            if not validate_battle_tag_format(battle_tag):
                await interaction.followup.send(
                    "❌ 올바르지 않은 배틀태그 형식입니다.\n"
                    "**형식**: `이름#1234` (예: backyerin#3538)",
                    ephemeral=True
                )
                return
            
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
            
            account_type_text = "본계정" if self.account_type == "main" else "부계정"
            success_msg = f"✅ **{battle_tag}** ({account_type_text}) 추가 완료!"
            if rank_info:
                success_msg += f"\n🎮 랭크 정보도 자동으로 저장되었습니다."
            
            await interaction.followup.send(success_msg, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 배틀태그 추가 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 배틀태그 추가 중 오류가 발생했습니다.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(TeamInfoCommands(bot))