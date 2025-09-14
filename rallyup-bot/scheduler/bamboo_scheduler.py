import asyncio
import aiosqlite
import discord
from datetime import datetime
from typing import List, Dict, Optional
from utils.time_utils import TimeUtils

class BambooForestScheduler:
    def __init__(self, bot):
        self.bot = bot
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
    async def start(self):
        """스케줄러 시작"""
        if self.running:
            print("🎋 스케줄러가 이미 실행 중입니다.")
            return
            
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        print("🎋 대나무숲 스케줄러가 시작되었습니다.")
        
    async def stop(self):
        """스케줄러 중지"""
        if not self.running:
            return
            
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        print("🎋 대나무숲 스케줄러가 중지되었습니다.")
        
    async def _scheduler_loop(self):
        """메인 스케줄러 루프 - 1분마다 실행"""
        while self.running:
            try:
                await self._process_pending_reveals()
                await asyncio.sleep(15)  # 15초 대기
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"🎋 스케줄러 오류: {e}")
                await asyncio.sleep(15)  # 오류 발생해도 계속 실행
                
    async def _process_pending_reveals(self):
        """공개할 메시지들 처리"""
        try:
            current_time = int(TimeUtils.get_utc_now().timestamp())

            # 공개 대기 중인 메시지들 조회
            pending_messages = await self.bot.db_manager.get_pending_reveals()
            
            if not pending_messages:
                return
                
            print(f"🎋 {len(pending_messages)}개 메시지 공개 처리 중...")
            
            for msg_data in pending_messages:
                await self._reveal_single_message(msg_data)
                await asyncio.sleep(0.5)  # 메시지 간 0.5초 간격
                
        except Exception as e:
            print(f"🎋 메시지 공개 처리 중 오류: {e}")
            
    async def _reveal_single_message(self, msg_data: Dict):
        """개별 메시지 실명 공개"""
        try:
            # Discord 객체들 가져오기
            guild = self.bot.get_guild(int(msg_data['guild_id']))
            if not guild:
                print(f"🎋 서버 없음: {msg_data['guild_id']}")
                return
                
            channel = guild.get_channel(int(msg_data['channel_id']))
            if not channel:
                print(f"🎋 채널 없음: {msg_data['channel_id']}")
                return
                
            # Discord 메시지 가져오기
            try:
                message = await channel.fetch_message(int(msg_data['message_id']))
            except discord.NotFound:
                # 메시지가 삭제된 경우 DB에서 공개됨으로 표시
                await self.bot.db_manager.mark_message_revealed(msg_data['message_id'])
                print(f"🎋 삭제된 메시지 처리 완료: {msg_data['message_id']}")
                return
            except discord.Forbidden:
                print(f"🎋 메시지 접근 권한 없음: {msg_data['message_id']}")
                return
                
            # 작성자 정보 가져오기
            author = None
            try:
                author = await self.bot.fetch_user(int(msg_data['author_id']))
            except:
                print(f"🎋 작성자를 찾을 수 없음: {msg_data['author_id']}")
                
            # 실명 공개 임베드 생성
            await self._create_revealed_message(message, msg_data, author, guild)
            
            # DB 업데이트
            await self.bot.db_manager.mark_message_revealed(msg_data['message_id'])
            
            # 작성자에게 알림
            if author:
                await self._send_reveal_notification(author, msg_data, guild, message)
                
            print(f"✅ 메시지 실명 공개 완료: {msg_data['message_id']}")
            
        except Exception as e:
            print(f"🎋 메시지 공개 중 오류 {msg_data.get('message_id', 'Unknown')}: {e}")
            
    async def _create_revealed_message(self, message: discord.Message, 
                                     msg_data: Dict, author: Optional[discord.User], 
                                     guild: discord.Guild):
        """공개된 메시지 임베드 생성 및 편집"""
        
        embed = discord.Embed(
            description=msg_data['original_content'],
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        if author:
            # 서버 멤버 정보 가져오기 (닉네임, 아바타 등)
            guild_member = guild.get_member(author.id)
            
            if guild_member:
                # 서버 내 닉네임과 아바타 사용
                display_name = guild_member.display_name
                avatar_url = guild_member.display_avatar.url
            else:
                # 서버에 없는 경우 기본 정보 사용
                display_name = author.display_name
                avatar_url = author.display_avatar.url
                
            embed.set_author(
                name=f"🎋 {display_name}",
                icon_url=avatar_url
            )
            
            # 작성자 멘션 추가
            embed.add_field(
                name="👤 작성자",
                value=f"<@{author.id}>",
                inline=True
            )
        else:
            embed.set_author(name="🎋 대나무숲 (알 수 없는 사용자)")
            embed.add_field(
                name="👤 작성자",
                value="*사용자를 찾을 수 없음*",
                inline=True
            )
        
        try:
            embed.add_field(
                name="✅ 공개 완료",
                value="실명으로 공개되었습니다",
                inline=True
            )
        except Exception as time_error:
            print(f"🎋 시간 파싱 오류: {time_error}")
            original_time = datetime.fromisoformat(msg_data['created_at'])
            embed.add_field(
                name="📅 시간 정보", 
                value=f"**작성**: <t:{int(original_time.timestamp())}:R>\n"
                    f"**공개**: <t:{int(datetime.now().timestamp())}:R>",
                inline=True
            )
        
        # embed.set_footer(text="⏰ 설정된 시간에 도달하여 실명으로 공개되었습니다")
        
        # 메시지 편집
        await message.edit(embed=embed)
        
    async def _send_reveal_notification(self, author: discord.User, 
                                      msg_data: Dict, guild: discord.Guild, 
                                      message: discord.Message):
        """작성자에게 공개 알림 DM 전송"""
        try:
            embed = discord.Embed(
                title="🎋 대나무숲 메시지 공개 알림",
                description=f"**{guild.name}**에서 작성하신 대나무숲 메시지가 실명으로 공개되었습니다.",
                color=0x00ff88
            )
            
            # 메시지 내용 (일부만)
            content_preview = msg_data['original_content'][:200]
            if len(msg_data['original_content']) > 200:
                content_preview += "..."
            embed.add_field(
                name="📝 공개된 메시지",
                value=f"```{content_preview}```",
                inline=False
            )
            
            embed.add_field(
                name="🔗 메시지 바로가기",
                value=f"[대나무숲에서 보기]({message.jump_url})",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="이제 해당 메시지에 회원님의 닉네임과 아바타가 표시됩니다.",
                inline=False
            )
            
            await author.send(embed=embed)
            
        except discord.Forbidden:
            # DM 차단된 경우 무시
            pass
        except Exception as e:
            print(f"🎋 공개 알림 전송 실패: {e}")
            
    async def force_reveal_message(self, message_id: str) -> bool:
        """관리자가 메시지를 강제로 즉시 공개"""
        try:
            # 메시지 정보 조회
            msg_data = await self.bot.db_manager.get_bamboo_message(message_id)
            if not msg_data:
                return False
                
            # 이미 공개된 메시지인지 확인
            if msg_data['is_revealed']:
                return False
                
            # 시간 공개 타입이 아니면 공개하지 않음
            if msg_data['message_type'] != 'timed_reveal':
                return False
                
            # 강제 공개 처리
            await self._reveal_single_message(msg_data)
            return True
            
        except Exception as e:
            print(f"🎋 강제 공개 중 오류: {e}")
            return False
            
    async def get_next_reveal_time(self, guild_id: str) -> Optional[int]:
        """다음 공개 예정 시간 반환"""
        try:
            current_time = int(TimeUtils.get_utc_now().timestamp())
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT MIN(reveal_time) FROM bamboo_messages 
                    WHERE guild_id = ? AND message_type = 'timed_reveal' 
                    AND is_revealed = FALSE AND reveal_time > ?
                ''', (guild_id, current_time)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row and row[0] else None
                    
        except Exception as e:
            print(f"🎋 다음 공개 시간 조회 오류: {e}")
            return None
            
    async def get_pending_count(self, guild_id: str) -> int:
        """공개 대기 중인 메시지 수"""
        try:
            current_time = int(TimeUtils.get_utc_now().timestamp())
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=30.0) as db:
                async with db.execute('''
                    SELECT COUNT(*) FROM bamboo_messages 
                    WHERE guild_id = ? AND message_type = 'timed_reveal' 
                    AND is_revealed = FALSE AND reveal_time > ?
                ''', (guild_id, current_time)) as cursor:
                    row = await cursor.fetchone()
                    return row[0] if row else 0
                    
        except Exception as e:
            print(f"🎋 대기 중인 메시지 수 조회 오류: {e}")
            return 0