import discord
from typing import Dict, List, Optional
from datetime import datetime

class BattleTagLogger:
    """배틀태그 활동 로깅 유틸리티"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def log_battle_tag_add(
        self, 
        guild_id: str, 
        user: discord.Member, 
        battle_tag: str,
        account_type: str,
        is_primary: bool,
        rank_info: Optional[Dict] = None
    ):
        """배틀태그 추가 로그"""
        try:
            # 로그 설정 확인
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            if not settings or not settings['log_channel_id'] or not settings['log_add']:
                return  # 로그 비활성화 또는 채널 미설정
            
            # 채널 조회
            channel = self.bot.get_channel(int(settings['log_channel_id']))
            
            if not channel:
                # 채널이 삭제됨 - 설정 초기화
                await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
                print(f"⚠️ 로그 채널 삭제됨 - 설정 초기화: {guild_id}")
                return
            
            # 임베드 생성
            embed = discord.Embed(
                title="✅ 배틀태그 추가",
                description=f"{user.mention}님이 새 배틀태그를 등록했습니다",
                color=0x00ff88,
                timestamp=datetime.now()
            )
            
            # 배틀태그 정보
            account_emoji = "⭐" if is_primary else "💫"
            account_label = "주계정" if is_primary else account_type
            
            embed.add_field(
                name="🎮 배틀태그",
                value=f"{account_emoji} `{battle_tag}` ({account_label})",
                inline=False
            )
            
            # 랭크 정보 (있는 경우)
            if rank_info and rank_info.get('ratings'):
                from utils.overwatch_api import OverwatchAPI
                rank_display = OverwatchAPI.format_rank_display(rank_info)
                
                # 간략 버전 (첫 2줄만)
                rank_lines = rank_display.split('\n')
                if len(rank_lines) > 3:
                    rank_text = '\n'.join(rank_lines[:3])
                else:
                    rank_text = rank_display.replace("**경쟁전 랭크**:\n", "")
                
                embed.add_field(
                    name="🏆 오버워치 랭크",
                    value=rank_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="🏆 오버워치 랭크",
                    value="랭크 정보 없음 (비공개 또는 미배치)",
                    inline=False
                )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(
                icon_url=user.display_avatar.url
            )
            
            # 로그 전송
            await channel.send(embed=embed)
            
        except discord.Forbidden:
            # 권한 없음 - 설정 초기화
            await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
            print(f"⚠️ 로그 채널 권한 없음 - 설정 초기화: {guild_id}")
            
        except Exception as e:
            print(f"❌ 배틀태그 추가 로그 전송 실패: {e}")
    
    async def log_battle_tag_delete(
        self,
        guild_id: str,
        user: discord.Member,
        battle_tag: str,
        was_primary: bool,
        new_primary_tag: Optional[str] = None
    ):
        """배틀태그 삭제 로그"""
        try:
            # 로그 설정 확인
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            if not settings or not settings['log_channel_id'] or not settings['log_delete']:
                return  # 로그 비활성화 또는 채널 미설정
            
            # 채널 조회
            channel = self.bot.get_channel(int(settings['log_channel_id']))
            
            if not channel:
                # 채널이 삭제됨 - 설정 초기화
                await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
                print(f"⚠️ 로그 채널 삭제됨 - 설정 초기화: {guild_id}")
                return
            
            # 임베드 생성
            embed = discord.Embed(
                title="❌ 배틀태그 삭제",
                description=f"{user.mention}님이 배틀태그를 삭제했습니다",
                color=0xff6b6b,
                timestamp=datetime.now()
            )
            
            # 삭제된 배틀태그 정보
            account_emoji = "⭐" if was_primary else "💫"
            account_label = "주계정" if was_primary else "부계정"
            
            embed.add_field(
                name="🗑️ 삭제된 배틀태그",
                value=f"{account_emoji} `{battle_tag}` ({account_label})",
                inline=False
            )
            
            # 주계정 자동 변경 안내
            if was_primary and new_primary_tag:
                embed.add_field(
                    name="🔄 주계정 자동 변경",
                    value=f"새 주계정: `{new_primary_tag}`",
                    inline=False
                )
            elif was_primary and not new_primary_tag:
                embed.add_field(
                    name="⚠️ 주계정 없음",
                    value="모든 배틀태그가 삭제되었습니다",
                    inline=False
                )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(
                text=f"유저 ID: {user.id}",
                icon_url=user.display_avatar.url
            )
            
            # 로그 전송
            await channel.send(embed=embed)
            
        except discord.Forbidden:
            # 권한 없음 - 설정 초기화
            await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
            print(f"⚠️ 로그 채널 권한 없음 - 설정 초기화: {guild_id}")
            
        except Exception as e:
            print(f"❌ 배틀태그 삭제 로그 전송 실패: {e}")
    
    async def notify_admin_log_error(self, guild_id: str, error_type: str):
        """관리자에게 로그 오류 알림 (선택사항)"""
        try:
            # 서버 관리자들 조회
            admins = await self.bot.db_manager.get_server_admins(guild_id)
            
            if not admins:
                return
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            # 오류 메시지
            error_messages = {
                'channel_deleted': '배틀태그 로그 채널이 삭제되어 로그 설정이 초기화되었습니다.',
                'no_permission': '배틀태그 로그 채널에 메시지 전송 권한이 없어 로그 설정이 초기화되었습니다.'
            }
            
            message = error_messages.get(error_type, '배틀태그 로그 전송 중 오류가 발생했습니다.')
            
            # 첫 번째 관리자에게만 DM (스팸 방지)
            if admins:
                admin_id = admins[0]['user_id']
                admin = guild.get_member(int(admin_id))
                
                if admin:
                    embed = discord.Embed(
                        title="⚠️ 배틀태그 로그 오류",
                        description=message,
                        color=0xffaa00,
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(
                        name="🔧 해결 방법",
                        value="`/배틀태그로그설정` 명령어로 로그 채널을 다시 설정해주세요.",
                        inline=False
                    )
                    
                    embed.set_footer(text=f"서버: {guild.name}")
                    
                    try:
                        await admin.send(embed=embed)
                    except:
                        pass  # DM 실패 시 무시
                        
        except Exception as e:
            print(f"❌ 관리자 알림 전송 실패: {e}")

    async def log_primary_change(
        self,
        guild_id: str,
        user: discord.Member,
        old_primary: str,
        new_primary: str,
        new_rank_info: Optional[Dict] = None
    ):
        """주계정 변경 로그"""
        try:
            # 로그 설정 확인
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            if not settings or not settings['log_channel_id'] or not settings['log_primary_change']:
                return  # 로그 비활성화
            
            # 채널 조회
            channel = self.bot.get_channel(int(settings['log_channel_id']))
            
            if not channel:
                await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
                return
            
            # 임베드 생성
            embed = discord.Embed(
                title="⭐ 주계정 변경",
                description=f"{user.mention}님이 주계정을 변경했습니다",
                color=0xffaa00,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🔄 변경 내역",
                value=f"이전: `{old_primary}`\n"
                      f"**→ 현재: `{new_primary}`**",
                inline=False
            )
            
            # 새 주계정 랭크 정보 (있는 경우)
            if new_rank_info and new_rank_info.get('ratings'):
                from utils.overwatch_api import OverwatchAPI
                rank_display = OverwatchAPI.format_rank_display(new_rank_info)
                
                rank_lines = rank_display.split('\n')
                if len(rank_lines) > 3:
                    rank_text = '\n'.join(rank_lines[:3])
                else:
                    rank_text = rank_display.replace("**경쟁전 랭크**:\n", "")
                
                embed.add_field(
                    name="🏆 새 주계정 랭크",
                    value=rank_text,
                    inline=False
                )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="닉네임 변경은 `/정보수정` 명령어를 사용하세요",
                inline=False
            )
            
            timestamp = int(datetime.now().timestamp())
            embed.add_field(
                name="⏰ 변경 시간",
                value=f"<t:{timestamp}:R>",
                inline=True
            )
            
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=f"유저 ID: {user.id}")
            
            await channel.send(embed=embed)
            
        except discord.Forbidden:
            await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
            
        except Exception as e:
            print(f"❌ 주계정 변경 로그 전송 실패: {e}")
    
    async def log_tier_change(
        self,
        guild_id: str,
        user_id: str,
        username: str,
        battle_tag: str,
        changes: List[Dict]
    ):
        """티어 변동 로그"""
        try:
            # 로그 설정 확인
            settings = await self.bot.db_manager.get_battle_tag_log_settings(guild_id)
            
            if not settings or not settings['log_channel_id'] or not settings['log_tier_change']:
                return  # 로그 비활성화
            
            # 채널 조회
            channel = self.bot.get_channel(int(settings['log_channel_id']))
            
            if not channel:
                await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
                return
            
            # 상승/하락 판단
            has_increase = any(c['direction'] == 'up' for c in changes)
            has_decrease = any(c['direction'] == 'down' for c in changes)
            
            if has_increase and not has_decrease:
                title = "📈 티어 상승"
                color = 0x00ff88
                emoji = "🎉"
            elif has_decrease and not has_increase:
                title = "📉 티어 하락"
                color = 0xff6b6b
                emoji = "😢"
            else:
                title = "🔄 티어 변동"
                color = 0xffaa00
                emoji = "📊"
            
            # 임베드 생성
            embed = discord.Embed(
                title=title,
                description=f"{emoji} **{username}**님의 티어가 변동되었습니다",
                color=color,
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="🎮 배틀태그",
                value=f"`{battle_tag}`",
                inline=False
            )
            
            # 변동 내역
            change_lines = []
            for change in changes:
                role_kr = {
                    'tank': '탱커',
                    'damage': '딜러',
                    'support': '힐러'
                }.get(change['role'], change['role'])
                
                direction_emoji = "📈" if change['direction'] == 'up' else "📉"
                
                change_lines.append(
                    f"{direction_emoji} **{role_kr}**: {change['old_tier']} → {change['new_tier']}"
                )
            
            embed.add_field(
                name="📊 변동 내역",
                value="\n".join(change_lines),
                inline=False
            )
            
            timestamp = int(datetime.now().timestamp())
            embed.add_field(
                name="⏰ 감지 시간",
                value=f"<t:{timestamp}:R>",
                inline=True
            )
            
            # 유저 아바타 (가능한 경우)
            guild = self.bot.get_guild(int(guild_id))
            if guild:
                member = guild.get_member(int(user_id))
                if member:
                    embed.set_thumbnail(url=member.display_avatar.url)
            
            embed.set_footer(text=f"자동 티어 감지 시스템")
            
            await channel.send(embed=embed)
            
        except discord.Forbidden:
            await self.bot.db_manager.reset_battle_tag_log_channel(guild_id)
            
        except Exception as e:
            print(f"❌ 티어 변동 로그 전송 실패: {e}")