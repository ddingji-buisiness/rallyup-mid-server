import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime, timedelta
from utils.time_utils import TimeUtils

class BambooForestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_admin(self, interaction: discord.Interaction) -> bool:
        """관리자 권한 확인 (서버 소유자 또는 등록된 관리자)"""
        guild_id = str(interaction.guild_id)
        user_id = str(interaction.user.id)
        
        # 서버 소유자는 항상 관리자
        if interaction.user.id == interaction.guild.owner_id:
            return True
        
        # 데이터베이스에서 관리자 확인
        return await self.bot.db_manager.is_server_admin(guild_id, user_id)

    async def get_bamboo_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """대나무숲 채널 찾기 (ID 기반)"""
        try:
            channel_id = await self.bot.db_manager.get_bamboo_channel(str(guild.id))
            if not channel_id:
                return None
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                # 채널이 삭제된 경우 DB에서 정보 제거
                await self.bot.db_manager.remove_bamboo_channel(str(guild.id))
                return None
                
            return channel
            
        except Exception as e:
            print(f"❌ 대나무숲 채널 조회 오류: {e}")
            return None
        
    async def _send_welcome_message(self, channel: discord.TextChannel):
        """환영 메시지 전송"""
        try:
            welcome_embed = discord.Embed(
                title="🎋 대나무숲에 오신 것을 환영합니다!",
                description="이곳은 익명으로 메시지를 남길 수 있는 특별한 공간입니다.",
                color=0x00ff88
            )
            
            welcome_embed.add_field(
                name="📝 사용 방법",
                value="1️⃣ `/대나무숲` 명령어로 메시지 작성\n"
                      "2️⃣ **완전 익명** 또는 **시간 후 실명** 선택\n"
                      "3️⃣ 메시지 자동 전송 및 공개",
                inline=False
            )
            
            welcome_embed.add_field(
                name="🔒 익명성 보장",
                value="• **완전 익명**: 영구적으로 익명 유지\n"
                      "• **시간 후 실명**: 설정 시간 후 닉네임+아바타 공개\n"
                      "• **관리자 조회**: 필요시 작성자 확인 가능",
                inline=False
            )
            
            welcome_embed.add_field(
                name="📋 이용 규칙",
                value="• 서로 존중하고 배려하는 마음으로 이용해주세요\n"
                      "• 부적절한 내용 발견 시 관리자에게 신고해주세요\n"
                      "• 메시지는 최대 2000자까지 작성 가능합니다",
                inline=False
            )
            
            welcome_embed.set_footer(text="💡 지금 바로 /대나무숲 명령어를 사용해보세요!")
            
            await channel.send(embed=welcome_embed)
            
        except Exception as e:
            print(f"❌ 환영 메시지 전송 실패: {e}")

    @app_commands.command(name="대나무숲설정", description="[관리자] 대나무숲 채널을 설정합니다")
    @app_commands.describe(
        채널="대나무숲으로 사용할 채널 (생략 시 새 채널 생성)",
        채널명="새 채널 생성 시 채널 이름 (기본값: 대나무숲)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def setup_bamboo_forest(
        self, 
        interaction: discord.Interaction, 
        채널: discord.TextChannel = None,
        채널명: str = "대나무숲"
    ):
        """대나무숲 설정 명령어"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            bamboo_channel = None
            
            if 채널:
                # 기존 채널을 대나무숲으로 설정
                bamboo_channel = 채널
                setup_type = "기존 채널 설정"
            else:
                # 새 채널 생성
                bamboo_channel = await interaction.guild.create_text_channel(
                    name=채널명,
                    topic="🎋 익명으로 메시지를 남기는 공간입니다. /대나무숲 명령어를 사용해보세요!",
                    reason="대나무숲 기능 설정"
                )
                setup_type = "새 채널 생성"
            
            # 데이터베이스에 채널 ID 저장
            success = await self.bot.db_manager.set_bamboo_channel(
                str(interaction.guild_id), 
                str(bamboo_channel.id)
            )
            
            if not success:
                await interaction.followup.send(
                    "❌ 대나무숲 설정 저장 중 오류가 발생했습니다.", ephemeral=True
                )
                return
            
            # 환영 메시지 전송 (새 채널인 경우만)
            if not 채널:
                await self._send_welcome_message(bamboo_channel)
            
            # 성공 응답
            embed = discord.Embed(
                title="✅ 대나무숲 설정 완료!",
                description=f"**{setup_type}**: <#{bamboo_channel.id}>",
                color=0x00ff88
            )
            
            embed.add_field(
                name="🎯 사용 가능한 명령어",
                value="• `/대나무숲 [메시지]` - 익명 메시지 작성\n"
                      "• `/대나무숲조회 [링크]` - 작성자 조회 (관리자)\n" 
                      "• `/대나무숲통계` - 사용 통계 (관리자)\n"
                      "• `/대나무숲강제공개 [링크]` - 강제 공개 (관리자)",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 시스템 상태", 
                value=f"**스케줄러**: {'🟢 실행 중' if self.bot.bamboo_scheduler.running else '🔴 중지됨'}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 채널 생성/수정 권한이 없습니다. 서버 관리 권한을 확인해주세요.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ 설정 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="대나무숲", description="익명으로 메시지를 남깁니다")
    @app_commands.describe(메시지="남길 메시지를 입력해주세요 (최대 2000자)")
    async def bamboo_forest(self, interaction: discord.Interaction, 메시지: str):
        """대나무숲 메인 명령어"""
        
        # 메시지 유효성 검사
        if not 메시지.strip():
            await interaction.response.send_message(
                "❌ 빈 메시지는 보낼 수 없습니다.", ephemeral=True
            )
            return
            
        if len(메시지) > 2000:
            await interaction.response.send_message(
                "❌ 메시지는 2000자 이하로 작성해주세요.", ephemeral=True
            )
            return
        
        # 대나무숲 채널 확인
        bamboo_channel = await self.get_bamboo_channel(interaction.guild)
        if not bamboo_channel:
            await interaction.response.send_message(
                "❌ 대나무숲 채널이 설정되지 않았습니다.\n"
                "관리자에게 `/대나무숲설정`으로 채널 설정을 요청해주세요.", 
                ephemeral=True
            )
            return
        
        # 선택 UI 표시
        view = BambooForestSelectionView(메시지, bamboo_channel)
        
        embed = discord.Embed(
            title="🎋 대나무숲 메시지 설정",
            description="메시지 공개 방식을 선택해주세요:",
            color=0x00ff88
        )
        
        # 메시지 미리보기
        preview = 메시지[:100] + ("..." if len(메시지) > 100 else "")
        embed.add_field(
            name="📝 메시지 미리보기",
            value=f"```{preview}```",
            inline=False
        )
        
        embed.add_field(
            name="🔒 완전 익명",
            value="• 영구적으로 익명 유지\n• 관리자는 작성자 확인 가능",
            inline=True
        )
        embed.add_field(
            name="⏰ 시간 후 실명",
            value="• 지정 시간 후 자동 공개\n• 닉네임 + 아바타 표시",
            inline=True
        )
        
        embed.set_footer(text="💡 5분 내에 선택해주세요")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="대나무숲정보", description="[관리자] 현재 대나무숲 설정 정보를 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def bamboo_info(self, interaction: discord.Interaction):
        """대나무숲 설정 정보 확인"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 현재 설정된 채널 확인
            bamboo_channel = await self.get_bamboo_channel(interaction.guild)
            
            embed = discord.Embed(
                title="🎋 대나무숲 설정 정보",
                color=0x00ff88
            )
            
            if bamboo_channel:
                embed.add_field(
                    name="📢 현재 대나무숲 채널",
                    value=f"<#{bamboo_channel.id}>\n"
                          f"**채널명**: {bamboo_channel.name}\n"
                          f"**채널 ID**: `{bamboo_channel.id}`",
                    inline=False
                )
                
                embed.add_field(
                    name="✅ 상태",
                    value="🟢 정상 작동",
                    inline=True
                )
            else:
                embed.add_field(
                    name="❌ 상태",
                    value="🔴 채널이 설정되지 않음",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 해결 방법",
                    value="`/대나무숲설정` 명령어로 채널을 설정해주세요",
                    inline=False
                )
            
            embed.add_field(
                name="⚙️ 시스템 상태", 
                value=f"**스케줄러**: {'🟢 실행 중' if self.bot.bamboo_scheduler.running else '🔴 중지됨'}",
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 정보 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="대나무숲해제", description="[관리자] 대나무숲 설정을 해제합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_bamboo_forest(self, interaction: discord.Interaction):
        """대나무숲 설정 해제"""
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 현재 설정 확인
            bamboo_channel = await self.get_bamboo_channel(interaction.guild)
            
            if not bamboo_channel:
                await interaction.followup.send(
                    "❌ 설정된 대나무숲 채널이 없습니다.", ephemeral=True
                )
                return
            
            # DB에서 설정 제거
            success = await self.bot.db_manager.remove_bamboo_channel(str(interaction.guild_id))
            
            if success:
                embed = discord.Embed(
                    title="✅ 대나무숲 설정 해제 완료",
                    description=f"<#{bamboo_channel.id}> 채널의 대나무숲 설정이 해제되었습니다.",
                    color=0xff6b6b
                )
                
                embed.add_field(
                    name="📝 안내",
                    value="• 채널은 삭제되지 않았습니다\n"
                          "• 기존 메시지는 그대로 유지됩니다\n"
                          "• `/대나무숲설정`으로 다시 설정할 수 있습니다",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ 설정 해제 중 오류가 발생했습니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 설정 해제 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="대나무숲조회", description="[관리자] 익명 메시지의 작성자를 조회합니다")
    @app_commands.describe(메시지링크="조회할 대나무숲 메시지의 링크")
    @app_commands.default_permissions(manage_guild=True) 
    async def bamboo_lookup(self, interaction: discord.Interaction, 메시지링크: str):
        """관리자 전용: 익명 메시지 작성자 조회"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # 메시지 ID 추출
            message_id = 메시지링크.split('/')[-1]
            
            # DB에서 메시지 조회
            bamboo_msg = await self.bot.db_manager.get_bamboo_message(message_id)
            if not bamboo_msg:
                await interaction.followup.send(
                    "❌ 해당 메시지를 대나무숲 기록에서 찾을 수 없습니다.", ephemeral=True
                )
                return
            
            # 작성자 정보 조회
            try:
                author = await self.bot.fetch_user(int(bamboo_msg['author_id']))
            except:
                author = None
            
            # 조회 결과 임베드 생성
            embed = discord.Embed(
                title="🔍 대나무숲 메시지 조회 결과",
                color=0xff9500,
                timestamp=TimeUtils.get_kst_now()
            )
            
            if author:
                embed.set_author(
                    name=f"{author.display_name} ({author.name})",
                    icon_url=author.display_avatar.url
                )
                embed.add_field(
                    name="👤 작성자 정보",
                    value=f"**사용자**: <@{author.id}>\n"
                          f"**ID**: `{author.id}`\n"
                          f"**가입일**: <t:{int(author.created_at.timestamp())}:F>",
                    inline=False
                )
            else:
                embed.add_field(
                    name="👤 작성자 정보",
                    value=f"**사용자 ID**: `{bamboo_msg['author_id']}`\n"
                          f"⚠️ 사용자를 찾을 수 없음 (탈퇴했을 수 있음)",
                    inline=False
                )
            
            # 메시지 정보
            try:
                created_at_utc = TimeUtils.parse_db_timestamp(bamboo_msg['created_at'])
                created_timestamp = int(created_at_utc.timestamp())
                
                embed.add_field(
                    name="📋 메시지 정보",
                    value=f"**작성일**: <t:{created_timestamp}:F>\n" 
                        f"**작성**: <t:{created_timestamp}:R>\n"     
                        f"**타입**: {bamboo_msg['message_type']}\n"
                        f"**공개 상태**: {'✅ 공개됨' if bamboo_msg['is_revealed'] else '🔒 익명'}",
                    inline=False
                )
            except Exception as time_error:
                print(f"시간 파싱 오류: {time_error}")
                embed.add_field(
                    name="📋 메시지 정보",
                    value=f"**작성일**: {bamboo_msg['created_at']} (원본)\n"
                        f"**타입**: {bamboo_msg['message_type']}\n"
                        f"**공개 상태**: {'✅ 공개됨' if bamboo_msg['is_revealed'] else '🔒 익명'}",
                    inline=False
                )
            
            # 시간 공개 정보 (해당하는 경우)
            if bamboo_msg['message_type'] == 'timed_reveal' and bamboo_msg['reveal_time']:
                reveal_status = "✅ 공개됨" if bamboo_msg['is_revealed'] else "⏳ 대기 중"
                embed.add_field(
                    name="⏰ 실명 공개 정보",
                    value=f"**예정 시간**: <t:{bamboo_msg['reveal_time']}:F>\n"
                          f"**상태**: {reveal_status}",
                    inline=False
                )
            
            # 원본 메시지
            content_preview = bamboo_msg['original_content'][:500]
            if len(bamboo_msg['original_content']) > 500:
                content_preview += "..."
            embed.add_field(
                name="📝 원본 메시지",
                value=f"```{content_preview}```",
                inline=False
            )
            
            embed.set_footer(text=f"조회자: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="대나무숲통계", description="[관리자] 대나무숲 사용 통계를 확인합니다")
    @app_commands.default_permissions(manage_guild=True)  
    async def bamboo_stats(self, interaction: discord.Interaction):
        """관리자 전용: 대나무숲 통계"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats = await self.bot.db_manager.get_bamboo_statistics(str(interaction.guild_id))
            
            embed = discord.Embed(
                title="📊 대나무숲 사용 통계",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="📈 전체 통계",
                value=f"**총 메시지**: {stats.get('total_messages', 0):,}개\n"
                      f"**완전 익명**: {stats.get('anonymous_messages', 0):,}개\n"
                      f"**시간 공개**: {stats.get('timed_messages', 0):,}개\n"
                      f"**이미 공개됨**: {stats.get('revealed_messages', 0):,}개",
                inline=False
            )
            
            embed.add_field(
                name="📅 최근 활동",
                value=f"**오늘**: {stats.get('today_messages', 0)}개\n"
                      f"**이번 주**: {stats.get('week_messages', 0)}개\n"
                      f"**이번 달**: {stats.get('month_messages', 0)}개",
                inline=True
            )
            
            embed.add_field(
                name="⏰ 대기 중",
                value=f"**공개 예정**: {stats.get('pending_reveals', 0)}개\n"
                      f"**다음 공개**: {stats.get('next_reveal', '없음')}",
                inline=True
            )
            
            embed.set_footer(text=f"조회자: {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 통계 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="대나무숲강제공개", description="[관리자] 시간 공개 메시지를 즉시 공개합니다")
    @app_commands.describe(메시지링크="즉시 공개할 메시지의 링크")
    @app_commands.default_permissions(manage_guild=True)
    async def force_reveal(self, interaction: discord.Interaction, 메시지링크: str):
        """관리자 전용: 메시지 강제 공개"""
        
        if not await self.is_admin(interaction):
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            message_id = 메시지링크.split('/')[-1]
            
            success = await self.bot.bamboo_scheduler.force_reveal_message(message_id)
            
            if success:
                await interaction.followup.send(
                    "✅ 메시지가 즉시 실명으로 공개되었습니다.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ 메시지를 찾을 수 없거나 이미 공개된 메시지입니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 강제 공개 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )


# UI 컴포넌트들
class BambooForestSelectionView(discord.ui.View):
    def __init__(self, message_content: str, bamboo_channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.message_content = message_content
        self.bamboo_channel = bamboo_channel

    @discord.ui.button(label="🔒 완전 익명", style=discord.ButtonStyle.secondary)
    async def anonymous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """완전 익명으로 전송"""
        await interaction.response.defer()
        await self.send_bamboo_message(interaction, "anonymous")

    @discord.ui.button(label="⏰ 시간 후 실명", style=discord.ButtonStyle.primary)
    async def timed_reveal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """시간 선택 Modal 표시"""
        modal = TimeSelectionModal(self.message_content, self.bamboo_channel)
        await interaction.response.send_modal(modal)

    async def send_bamboo_message(self, interaction: discord.Interaction, 
                                message_type: str, reveal_time: Optional[int] = None):
        """대나무숲 메시지 전송"""
        try:
            # 임베드 생성
            if message_type == "timed_reveal" and reveal_time:
                embed = discord.Embed(
                    description=self.message_content,
                    color=0xff9500,
                    timestamp=datetime.now()
                )
                embed.set_author(name="🎋 대나무숲 (익명)")
                
                embed.add_field(
                    name="⏰ 실명 공개 예정",
                    value=f"**제출 시간**: <t:{reveal_time}:F>",
                    inline=False
                )
                embed.set_footer(text="🔒 현재는 익명 상태입니다")
                
            else:
                embed = discord.Embed(
                    description=self.message_content,
                    color=0x4287f5,
                    timestamp=datetime.now()
                )
                embed.set_author(name="🎋 대나무숲 (완전 익명)")
                embed.set_footer(text="🔒 영구 익명 (관리자 조회 가능)")
            
            # 메시지 전송
            sent_message = await self.bamboo_channel.send(embed=embed)
            
            # DB 저장
            success = await interaction.client.db_manager.save_bamboo_message(
                guild_id=str(interaction.guild.id),
                channel_id=str(self.bamboo_channel.id),
                message_id=str(sent_message.id),
                author_id=str(interaction.user.id),
                original_content=self.message_content,
                message_type=message_type,
                reveal_time=reveal_time
            )
            
            if success:
                # 성공 메시지
                success_embed = discord.Embed(
                    title="✅ 대나무숲 메시지 전송 완료!",
                    description=f"<#{self.bamboo_channel.id}>에 메시지가 전송되었습니다.",
                    color=0x00ff88
                )
                
                success_embed.add_field(
                    name="📋 전송 정보",
                    value=f"**메시지**: [바로가기]({sent_message.jump_url})\n"
                        f"**타입**: {'⏰ 시간 후 공개' if message_type == 'timed_reveal' else '🔒 완전 익명'}",
                    inline=False
                )
                
                if message_type == "timed_reveal" and reveal_time:                    
                    success_embed.add_field(
                        name="⏰ 실명 공개 예정",
                        value=f"**제출 시간**: <t:{reveal_time}:F>\n",
                        inline=False
                    )
                    success_embed.add_field(
                        name="🎭 공개 내용",
                        value="• 현재 서버 닉네임 표시\n• 현재 아바타 표시\n• 작성자 멘션 추가",
                        inline=False
                    )
                
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ 메시지 전송은 성공했지만 데이터베이스 저장에 실패했습니다.", ephemeral=True
                )
                
        except Exception as e:
            await interaction.followup.send(
                f"❌ 메시지 전송 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )


class TimeSelectionModal(discord.ui.Modal, title="⏰ 실명 공개 시간 설정"):
    def __init__(self, message_content: str, bamboo_channel: discord.TextChannel):
        super().__init__()
        self.message_content = message_content
        self.bamboo_channel = bamboo_channel

    time_input = discord.ui.TextInput(
        label="공개 시간 (분 단위)",
        placeholder="예: 60 (1시간), 180 (3시간), 1440 (24시간)",
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.time_input.value)
            
            # 시간 범위 검증
            if minutes < 1:
                await interaction.response.send_message(
                    "❌ 최소 1분 후에 공개 가능합니다.", ephemeral=True
                )
                return
            elif minutes > 10080:  # 7일
                await interaction.response.send_message(
                    "❌ 최대 7일(10080분) 후까지만 설정 가능합니다.", ephemeral=True
                )
                return
            
            # 공개 시간 계산
            reveal_datetime_utc = TimeUtils.get_utc_now() + timedelta(minutes=minutes)
            reveal_time = int(reveal_datetime_utc.timestamp())
            
            # 확인 UI 표시
            embed = discord.Embed(
                title="⏰ 실명 공개 시간 확인",
                description=f"**{minutes}분 후**에 실명으로 공개됩니다.",
                color=0xff9500
            )
            
            if minutes < 60:
                time_text = f"{minutes}분 후"
            elif minutes < 1440:
                hours = minutes // 60
                mins = minutes % 60
                time_text = f"{hours}시간" + (f" {mins}분" if mins > 0 else "") + " 후"
            else:
                days = minutes // 1440
                hours = (minutes % 1440) // 60
                time_text = f"{days}일" + (f" {hours}시간" if hours > 0 else "") + " 후"

            embed.add_field(
                name="📅 공개 예정 시간",
                value=f"**제출 시간**: <t:{reveal_time}:F>\n"
                    f"**설정**: {time_text}", 
                inline=False
            )
            
            preview = self.message_content[:200]
            if len(self.message_content) > 200:
                preview += "..."
            embed.add_field(
                name="📝 메시지",
                value=f"```{preview}```",
                inline=False
            )
            
            view = ConfirmationView(self.message_content, self.bamboo_channel, reveal_time)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ 올바른 숫자를 입력해주세요.", ephemeral=True
            )


class ConfirmationView(discord.ui.View):
    def __init__(self, message_content: str, bamboo_channel: discord.TextChannel, reveal_time: int):
        super().__init__(timeout=60)
        self.message_content = message_content
        self.bamboo_channel = bamboo_channel
        self.reveal_time = reveal_time

    @discord.ui.button(label="✅ 확인 및 전송", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """확인 후 메시지 전송"""
        await interaction.response.defer()
        
        bamboo_view = BambooForestSelectionView(self.message_content, self.bamboo_channel)
        await bamboo_view.send_bamboo_message(
            interaction, "timed_reveal", self.reveal_time
        )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """취소"""
        embed = discord.Embed(
            title="❌ 전송 취소",
            description="메시지 전송이 취소되었습니다.",
            color=0xff4444
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ChannelCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="✅ 채널 생성", style=discord.ButtonStyle.success)
    async def create_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """대나무숲 채널 생성"""
        await interaction.response.defer()
        
        try:
            # 채널 생성
            bamboo_channel = await interaction.guild.create_text_channel(
                name="대나무숲",
                topic="🎋 익명으로 메시지를 남기는 공간입니다. /대나무숲 명령어를 사용해보세요!",
                reason="대나무숲 기능 초기 설정"
            )
            
            # 환영 메시지 전송
            welcome_embed = discord.Embed(
                title="🎋 대나무숲에 오신 것을 환영합니다!",
                description="이곳은 익명으로 메시지를 남길 수 있는 특별한 공간입니다.",
                color=0x00ff88
            )
            
            welcome_embed.add_field(
                name="📝 사용 방법",
                value="1️⃣ `/대나무숲` 명령어로 메시지 작성\n"
                      "2️⃣ **완전 익명** 또는 **시간 후 실명** 선택\n"
                      "3️⃣ 메시지 자동 전송 및 공개",
                inline=False
            )
            
            welcome_embed.add_field(
                name="🔒 익명성 보장",
                value="• **완전 익명**: 영구적으로 익명 유지\n"
                      "• **시간 후 실명**: 설정 시간 후 닉네임+아바타 공개\n"
                      "• **관리자 조회**: 필요시 작성자 확인 가능",
                inline=False
            )
            
            welcome_embed.add_field(
                name="📋 이용 규칙",
                value="• 서로 존중하고 배려하는 마음으로 이용해주세요\n"
                      "• 부적절한 내용 발견 시 관리자에게 신고해주세요\n"
                      "• 메시지는 최대 2000자까지 작성 가능합니다",
                inline=False
            )
            
            welcome_embed.set_footer(text="💡 지금 바로 /대나무숲 명령어를 사용해보세요!")
            
            await bamboo_channel.send(embed=welcome_embed)
            
            # 성공 응답
            success_embed = discord.Embed(
                title="✅ 대나무숲 설정 완료!",
                description=f"<#{bamboo_channel.id}> 채널이 생성되었습니다!",
                color=0x00ff88
            )
            
            success_embed.add_field(
                name="🎯 다음 단계",
                value="• 이제 `/대나무숲` 명령어를 사용할 수 있습니다\n"
                      "• 채널에서 환영 메시지를 확인해보세요\n"
                      "• 테스트 메시지를 보내보세요!",
                inline=False
            )
            
            await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ 채널 생성 권한이 없습니다. 서버 관리 권한을 확인해주세요.", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ 채널 생성 중 오류가 발생했습니다: {str(e)}", ephemeral=True
            )

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger)
    async def cancel_create(self, interaction: discord.Interaction, button: discord.ui.Button):
        """취소"""
        embed = discord.Embed(
            title="❌ 설정 취소",
            description="대나무숲 채널 생성이 취소되었습니다.",
            color=0xff4444
        )
        await interaction.response.edit_message(embed=embed, view=None)


async def setup(bot):
    await bot.add_cog(BambooForestCommands(bot))