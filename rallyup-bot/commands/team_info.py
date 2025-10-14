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
        self.channel_messages: Dict[str, Dict[str, int]] = {}
        self.update_tasks: Dict[str, Dict[str, asyncio.Task]] = {}  
        self.active_guilds: set = set()
        self.resend_threshold = 10

    @commands.Cog.listener()
    async def on_ready(self):
        """봇 시작 시 DB에서 음성 모니터링 설정 로드"""
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT guild_id FROM voice_monitor_settings
                    WHERE enabled = TRUE
                ''') as cursor:
                    rows = await cursor.fetchall()
                    
                    for row in rows:
                        self.active_guilds.add(row[0])
                    
                    if rows:
                        print(f"✅ 음성 모니터링 설정 자동 로드: {len(rows)}개 서버")
                    else:
                        print(f"ℹ️ 활성화된 음성 모니터링 서버 없음")
                        
        except Exception as e:
            print(f"⚠️ 음성 모니터링 설정 로드 실패: {e}")
    
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
            await self._schedule_update(before.channel, allow_resend=False)
        
        # after 채널 업데이트
        if after.channel:
            await self._schedule_update(after.channel, allow_resend=True)
    
    async def _schedule_update(self, voice_channel: discord.VoiceChannel, delay: float = 2.0, allow_resend: bool = True):
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
            self._delayed_update(voice_channel, delay, allow_resend)  # ← 전달!
        )

    async def _delayed_update(self, voice_channel: discord.VoiceChannel, delay: float, allow_resend: bool):
        """지연된 업데이트 실행"""
        try:
            await asyncio.sleep(delay)
            await self._auto_update_team_info(voice_channel, allow_resend)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ 자동 팀정보 업데이트 오류: {e}")
    
    async def _auto_update_team_info(self, voice_channel: discord.VoiceChannel, allow_resend: bool = True):
        """팀정보 자동 업데이트 (음성 모니터링용) - 스마트 하이브리드 방식"""
        try:
            guild_id = str(voice_channel.guild.id)
            channel_id = str(voice_channel.id)
            
            # 1. 멤버 확인
            members = [m for m in voice_channel.members if not m.bot]
            
            # 2. 텍스트 채널 찾기 (같은 이름 + 권한 체크)
            text_channel = await self._find_text_channel(voice_channel)
            if not text_channel:
                print(f"ℹ️ 팀정보 발송 불가: {voice_channel.name} (권한 부족 또는 채널 접근 불가)")
                return
            
            # 3. 멤버 정보 수집
            members_info = await self._collect_members_info(guild_id, members)
            avg_tier = self._calculate_average_tier(members_info)
            
            # 4. 임베드 생성
            embed = self._create_team_embed(voice_channel, members_info, avg_tier, 0, is_manual=False)
            
            # 5. 스마트 하이브리드: Edit vs Delete+Resend 결정
            if guild_id in self.channel_messages and channel_id in self.channel_messages[guild_id]:
                # 기존 메시지 존재
                message_id = self.channel_messages[guild_id][channel_id]
                
                try:
                    old_message = await text_channel.fetch_message(message_id)
                    
                    # 멤버 없으면 삭제
                    if not members:
                        await old_message.delete()
                        del self.channel_messages[guild_id][channel_id]
                        return
                    
                    # 🎯 스마트 결정: 마지막 팀정보 이후 메시지 개수 체크
                    should_resend = await self._should_resend_message(text_channel, old_message)
                    
                    if should_resend and allow_resend:
                        # 재발송: 삭제 후 새로 발송 (채팅 많을 때)
                        await old_message.delete()
                        view = AutoTeamInfoView(voice_channel, members_info, avg_tier, self.bot, self)
                        new_message = await text_channel.send(embed=embed, view=view)
                        self.channel_messages[guild_id][channel_id] = new_message.id
                        print(f"🔄 팀정보 재발송: {voice_channel.name} (채팅 {self.resend_threshold}개 이상)")
                    else:
                        # Edit: 조용히 수정 (채팅 적을 때)
                        view = AutoTeamInfoView(voice_channel, members_info, avg_tier, self.bot, self)
                        await old_message.edit(embed=embed, view=view)
                        print(f"✏️ 팀정보 수정: {voice_channel.name}")
                    
                except discord.NotFound:
                    # 메시지가 삭제됨 - 새로 생성
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
                    print(f"📨 팀정보 신규 발송: {voice_channel.name}")
        
        except discord.Forbidden:
            print(f"❌ 예상치 못한 권한 오류: {voice_channel.name}")
        except Exception as e:
            print(f"❌ 자동 팀정보 업데이트 실패: {voice_channel.name} - {e}")
            import traceback
            traceback.print_exc()

    async def _should_resend_message(
        self, 
        text_channel: discord.abc.Messageable, 
        old_message: discord.Message
    ) -> bool:
        try:
            # 마지막 팀정보 메시지 이후의 메시지 개수 세기
            messages_after = 0
            
            async for message in text_channel.history(limit=50, after=old_message.created_at):
                # 봇 메시지는 제외 (팀정보 메시지 제외)
                if not message.author.bot:
                    messages_after += 1
            
            # 임계값 이상이면 재발송
            return messages_after >= self.resend_threshold
            
        except Exception as e:
            print(f"⚠️ 메시지 카운트 실패: {e}")
            # 오류 시 안전하게 Edit 선택
            return False
    
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
            
            # DB에 저장
            await self._save_voice_monitor_setting(guild_id, 활성화)
            
            # 캐시 업데이트
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
                      "• 음성 채널의 내장 텍스트 채널에 자동 발송\n"
                      "• 모든 유저 퇴장 시 메시지 자동 삭제",
                inline=False
            )
            
            if 활성화:
                embed.add_field(
                    name="💡 중요 안내",
                    value="• 디스코드 음성 채널은 자동으로 텍스트 기능이 있습니다\n"
                          "• **별도의 텍스트 채널을 만들 필요가 없습니다**\n"
                          "• 봇에게 음성 채널의 '메시지 보내기' 권한만 부여하세요\n"
                          "• 음성 참가자들만 팀정보 메시지를 볼 수 있습니다",
                    inline=False
                )
            
            embed.add_field(
                name="🔍 상태 확인",
                value="`/음성진단` 명령어로 현재 설정을 확인할 수 있습니다",
                inline=False
            )
            
            embed.set_footer(text="RallyUp Bot | 음성 채널 모니터링")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 설정 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )
    
    async def _save_voice_monitor_setting(self, guild_id: str, enabled: bool):
        """음성 모니터링 설정을 DB에 저장"""
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # UPSERT (있으면 업데이트, 없으면 삽입)
                await db.execute('''
                    INSERT INTO voice_monitor_settings (guild_id, enabled)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        enabled = excluded.enabled,
                        updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, enabled))
                
                await db.commit()
                print(f"✅ 음성 모니터링 설정 저장: {guild_id} = {enabled}")
                
        except Exception as e:
            print(f"❌ 음성 모니터링 설정 저장 실패: {e}")
            raise
    
    @app_commands.command(name="음성진단", description="음성 채널 자동 모니터링 상태를 확인합니다")
    async def voice_monitor_status(self, interaction: discord.Interaction):
        """음성 모니터링 상태 확인"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild_id)
            
            # DB에서 설정 조회
            is_enabled = await self._get_voice_monitor_setting(guild_id)
            
            # 캐시와 DB 동기화 확인
            in_cache = guild_id in self.active_guilds
            
            embed = discord.Embed(
                title="🔍 음성 모니터링 진단",
                color=0x00ff88 if is_enabled else 0x666666,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📊 모니터링 상태",
                value=f"**활성화**: {'✅ 켜짐' if is_enabled else '⬜ 꺼짐'}\n"
                      f"**캐시**: {'✅ 로드됨' if in_cache else '⚠️ 미로드'}\n"
                      f"**동기화**: {'✅ 정상' if (is_enabled == in_cache) else '❌ 불일치'}",
                inline=False
            )
            
            if not is_enabled:
                embed.add_field(
                    name="⚙️ 활성화 명령어",
                    value="`/음성모니터 활성화:True`",
                    inline=False
                )
            
            # 음성 채널 분석
            voice_channels = interaction.guild.voice_channels
            bot_member = interaction.guild.get_member(self.bot.user.id)
            
            available_channels = []
            no_permission_channels = []
            
            for vc in voice_channels:
                member_count = len([m for m in vc.members if not m.bot])
                
                # 권한 체크
                perms = vc.permissions_for(bot_member)
                has_permission = perms.send_messages and perms.embed_links and perms.view_channel
                
                if has_permission:
                    available_channels.append(f"• {vc.name} ({member_count}명) ✅")
                else:
                    no_permission_channels.append(f"• {vc.name} ({member_count}명) ❌ 권한 없음")
            
            if is_enabled:
                if available_channels:
                    # 최대 15개만 표시
                    display_list = available_channels[:15]
                    remaining = len(available_channels) - 15
                    
                    embed.add_field(
                        name=f"✅ 모니터링 가능 채널 ({len(available_channels)}개)",
                        value="\n".join(display_list) + 
                              (f"\n... 외 {remaining}개 채널" if remaining > 0 else ""),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="⚠️ 모니터링 가능 채널",
                        value="모든 음성 채널에 권한이 없습니다",
                        inline=False
                    )
                
                if no_permission_channels:
                    display_list = no_permission_channels[:5]
                    remaining = len(no_permission_channels) - 5
                    
                    embed.add_field(
                        name=f"❌ 권한 없는 채널 ({len(no_permission_channels)}개)",
                        value="\n".join(display_list) +
                              (f"\n... 외 {remaining}개" if remaining > 0 else ""),
                        inline=False
                    )
            
            # 활성 메시지 개수
            active_messages = 0
            if guild_id in self.channel_messages:
                active_messages = len(self.channel_messages[guild_id])
            
            embed.add_field(
                name="📨 활성 모니터링 메시지",
                value=f"{active_messages}개 채널에서 활성 중",
                inline=False
            )
            
            embed.add_field(
                name="💡 안내",
                value="• 모든 음성 채널은 자동으로 텍스트 채널 기능이 있습니다\n"
                      "• 별도의 텍스트 채널을 만들 필요가 없습니다\n"
                      "• 봇에게 음성 채널의 '메시지 보내기' 권한만 있으면 됩니다",
                inline=False
            )
            
            embed.set_footer(text="문제가 있는 채널은 권한을 확인해주세요")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 음성진단 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 상태 확인 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )
    
    async def _get_voice_monitor_setting(self, guild_id: str) -> bool:
        """DB에서 음성 모니터링 설정 조회"""
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT enabled FROM voice_monitor_settings
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    return bool(row[0]) if row else False
                    
        except Exception as e:
            print(f"⚠️ 음성 모니터링 설정 조회 실패: {e}")
            return False
        
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
    
    async def _find_text_channel(self, voice_channel: discord.VoiceChannel) -> Optional[discord.abc.Messageable]:
        """
        음성 채널에 대응하는 텍스트 채널 찾기
        1순위: 음성 채널 자체 (내장 텍스트 채널 기능)
        2순위: 같은 이름의 독립 텍스트 채널
        
        Returns:
            VoiceChannel (내장 텍스트) 또는 TextChannel (독립 채널)
        """
        guild = voice_channel.guild
        bot_member = guild.get_member(self.bot.user.id)
        
        # 1. 음성 채널 자체가 텍스트 메시지를 받을 수 있는지 확인
        # discord.VoiceChannel은 Messageable을 상속하므로 직접 메시지 보낼 수 있음
        try:
            voice_perms = voice_channel.permissions_for(bot_member)
            if voice_perms.send_messages and voice_perms.embed_links and voice_perms.view_channel:
                # 음성 채널 자체를 텍스트 채널로 사용 (내장 텍스트 채널)
                return voice_channel
        except Exception as e:
            print(f"⚠️ 음성 채널 권한 확인 실패: {voice_channel.name} - {e}")
        
        # 2. 같은 이름의 독립 텍스트 채널 찾기
        for channel in guild.text_channels:
            if channel.name.lower() == voice_channel.name.lower():
                # 권한 체크
                text_perms = channel.permissions_for(bot_member)
                if text_perms.send_messages and text_perms.embed_links:
                    return channel
                else:
                    print(f"⚠️ 텍스트 채널 권한 없음: {channel.name}")
                    return None
        
        # 아무것도 찾지 못함
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
            title=f"{voice_channel.name} 팀 정보{page_info}",
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
            
            member_lines.append(f"\n👤 <@{member.id}>{tier_display}")
            
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
            embed.set_footer(text="위 코드블록을 드래그하여 복사하세요")
        
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
        self.total_pages = math.ceil(len(members_info) / self.members_per_page) if members_info else 1
        
        # 버튼 초기 상태 설정
        self._setup_buttons()
    
    def _setup_buttons(self):
        """버튼 초기 설정"""
        # 페이지가 1개면 페이징 버튼 제거
        if self.total_pages <= 1:
            # 이전/다음 버튼 찾아서 제거
            items_to_remove = []
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id in ["prev_manual", "next_manual"]:
                    items_to_remove.append(item)
            for item in items_to_remove:
                self.remove_item(item)
        else:
            # 버튼 상태 업데이트
            self.update_buttons()
    
    def update_buttons(self):
        """버튼 상태 업데이트"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "prev_manual":
                    item.disabled = (self.current_page == 0)
                elif item.custom_id == "next_manual":
                    item.disabled = (self.current_page >= self.total_pages - 1)
    
    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev_manual", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=True
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="배틀태그 추가", style=discord.ButtonStyle.success, emoji="➕", custom_id="add_tag_manual", row=0)
    async def add_battle_tag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """배틀태그 추가"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 등록된 유저인지 확인
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
        
        # 계정 타입 선택 View
        view = AccountTypeSelectView(self, self.bot, self.cog)
        await interaction.response.send_message(
            "**계정 타입을 선택해주세요:**",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next_manual", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=True
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    async def on_timeout(self):
        """타임아웃 시 버튼 비활성화"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True


class AutoTeamInfoView(discord.ui.View):
    """자동 음성 모니터링용 View"""
    
    def __init__(self, voice_channel: discord.VoiceChannel, members_info: List[Dict], avg_tier: str, bot, cog):
        super().__init__(timeout=None)  # 타임아웃 없음 (자동 업데이트)
        self.voice_channel = voice_channel
        self.members_info = members_info
        self.avg_tier = avg_tier
        self.bot = bot
        self.cog = cog
        self.current_page = 0
        self.members_per_page = 5
        self.total_pages = math.ceil(len(members_info) / self.members_per_page) if members_info else 1
        
        # 버튼 초기 설정
        self._setup_buttons()
    
    def _setup_buttons(self):
        """버튼 초기 설정"""
        # 페이지가 1개면 페이징 버튼 제거
        if self.total_pages <= 1:
            items_to_remove = []
            for item in self.children:
                if isinstance(item, discord.ui.Button) and item.custom_id in ["prev_auto", "next_auto"]:
                    items_to_remove.append(item)
            for item in items_to_remove:
                self.remove_item(item)
        else:
            self.update_buttons()
    
    def update_buttons(self):
        """버튼 상태 업데이트"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == "prev_auto":
                    item.disabled = (self.current_page == 0)
                elif item.custom_id == "next_auto":
                    item.disabled = (self.current_page >= self.total_pages - 1)
    
    @discord.ui.button(label="이전", style=discord.ButtonStyle.secondary, emoji="⬅️", custom_id="prev_auto", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """이전 페이지"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=False
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="배틀태그 추가", style=discord.ButtonStyle.primary, emoji="➕", custom_id="add_tag_auto", row=0)
    async def add_battle_tag_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """배틀태그 추가"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 등록된 유저인지 확인
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
        
        # 계정 타입 선택 View
        view = AccountTypeSelectView(self, self.bot, self.cog)
        await interaction.response.send_message(
            "**계정 타입을 선택해주세요:**",
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="다음", style=discord.ButtonStyle.secondary, emoji="➡️", custom_id="next_auto", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """다음 페이지"""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.cog._create_team_embed(
                self.voice_channel, self.members_info, self.avg_tier, self.current_page, is_manual=False
            )
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()


class AccountTypeSelectView(discord.ui.View):
    """계정 타입 선택 View"""
    
    def __init__(self, parent_view, bot, cog):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.bot = bot
        self.cog = cog
    
    @discord.ui.button(label="본계정", style=discord.ButtonStyle.primary, emoji="⭐")
    async def main_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """본계정 선택"""
        modal = AddBattleTagModal(self.parent_view, self.bot, self.cog, "main")
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="부계정", style=discord.ButtonStyle.secondary, emoji="💫")
    async def sub_account_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """부계정 선택"""
        modal = AddBattleTagModal(self.parent_view, self.bot, self.cog, "sub")
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
    
    def __init__(self, parent_view, bot, cog, account_type: str):
        super().__init__()
        self.parent_view = parent_view
        self.bot = bot
        self.cog = cog
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
            
            # 임베드 새로고침
            if isinstance(self.parent_view, TeamInfoPaginationView):
                # 수동 /팀정보 명령어
                await self._refresh_manual_team_info(interaction)
            elif isinstance(self.parent_view, AutoTeamInfoView):
                # 자동 음성 모니터링
                await self._refresh_auto_team_info(interaction)
            
        except Exception as e:
            print(f"❌ 배틀태그 추가 오류: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ 배틀태그 추가 중 오류가 발생했습니다.",
                ephemeral=True
            )
    
    async def _refresh_manual_team_info(self, interaction: discord.Interaction):
        """수동 /팀정보 명령어 임베드 새로고침"""
        try:
            voice_channel = self.parent_view.voice_channel
            guild_id = str(interaction.guild_id)
            
            # 음성 채널의 모든 멤버 정보 다시 조회
            members = [m for m in voice_channel.members if not m.bot]
            members_info = await self.cog._collect_members_info(guild_id, members)
            avg_tier = self.cog._calculate_average_tier(members_info)
            
            # View 업데이트
            self.parent_view.members_info = members_info
            self.parent_view.avg_tier = avg_tier
            self.parent_view.total_pages = math.ceil(len(members_info) / self.parent_view.members_per_page) if members_info else 1
            
            # 현재 페이지가 범위를 벗어나면 조정
            if self.parent_view.current_page >= self.parent_view.total_pages:
                self.parent_view.current_page = max(0, self.parent_view.total_pages - 1)
            
            # 버튼 재설정
            self.parent_view._setup_buttons()
            
            # 임베드 재생성
            embed = self.cog._create_team_embed(
                voice_channel, members_info, avg_tier, self.parent_view.current_page, is_manual=True
            )
            
            # 원본 메시지 찾아서 수정
            async for msg in interaction.channel.history(limit=20):
                if msg.author == self.bot.user and len(msg.embeds) > 0:
                    embed_title = msg.embeds[0].title
                    if voice_channel.name in embed_title and "팀 정보" in embed_title:
                        await msg.edit(embed=embed, view=self.parent_view)
                        break
            
        except Exception as e:
            print(f"❌ 수동 팀정보 새로고침 오류: {e}")
            import traceback
            traceback.print_exc()
    
    async def _refresh_auto_team_info(self, interaction: discord.Interaction):
        """자동 음성 모니터링 메시지 새로고침"""
        try:
            voice_channel = self.parent_view.voice_channel
            
            # 자동 업데이트 트리거 (기존 로직 재사용)
            await self.cog._auto_update_team_info(voice_channel)
            
        except Exception as e:
            print(f"❌ 자동 팀정보 새로고침 오류: {e}")
            import traceback
            traceback.print_exc()


async def setup(bot):
    await bot.add_cog(TeamInfoCommands(bot))