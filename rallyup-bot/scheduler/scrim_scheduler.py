import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import discord

logger = logging.getLogger(__name__)

class ScrimScheduler:
    """길드 간 스크림 모집 스케줄러 - 마감된 모집 자동 처리"""
    
    def __init__(self, bot):
        self.bot = bot
        self.task = None
        self.running = False
    
    async def start(self):
        """스케줄러 시작"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("🎯 길드 간 스크림 스케줄러가 시작되었습니다.")
    
    async def stop(self):
        """스케줄러 중지"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🎯 길드 간 스크림 스케줄러가 중지되었습니다.")
    
    async def _scheduler_loop(self):
        """스케줄러 메인 루프"""
        while self.running:
            try:
                await self._process_expired_scrims()
                await asyncio.sleep(60)  # 1분마다 체크
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"🚨 길드 간 스크림 스케줄러 오류: {e}")
                await asyncio.sleep(60)
    
    async def _process_expired_scrims(self):
        """만료된 길드 간 스크림 모집 처리"""
        try:
            expired_scrims = await self.bot.db_manager.get_expired_scrims()
            
            if expired_scrims:
                logger.info(f"🎯 {len(expired_scrims)}개의 만료된 길드 간 스크림 모집을 처리합니다.")
            
            for scrim in expired_scrims:
                await self._close_scrim(scrim)
                
        except AttributeError as e:
            logger.error(f"🚨 Repository 속성 오류: {e}")
            logger.error("inter_guild_scrim_repository가 DatabaseManager에 제대로 초기화되었는지 확인하세요.")
        except Exception as e:
            logger.error(f"🚨 만료된 길드 간 스크림 처리 오류: {e}")
    
    async def _close_scrim(self, scrim: Dict[str, Any]):
        """개별 길드 간 스크림 모집 마감 처리"""
        try:
            scrim_id = scrim['id']
            scrim_title = scrim.get('title', '제목 없음')
            
            # 상태를 'closed'로 변경
            success = await self.bot.db_manager.update_scrim_status(
                scrim_id, 'closed'
            )
            
            if success:
                logger.info(f"🎯 길드 간 스크림 모집 자동 마감: {scrim_title} (ID: {scrim_id})")
                
                # 선택사항: 참가자들에게 마감 알림 (필요시)
                await self._notify_scrim_closure(scrim)
            else:
                logger.warning(f"⚠️ 길드 간 스크림 상태 업데이트 실패: {scrim_id}")
            
        except Exception as e:
            logger.error(f"🚨 길드 간 스크림 마감 처리 오류: {e}")
            logger.error(f"문제가 된 스크림: {scrim}")
    
    async def _notify_scrim_closure(self, scrim: Dict[str, Any]):
        """길드 간 스크림 마감 알림 (선택사항)"""
        try:
            scrim_id = scrim['id']
            guild_id = scrim['guild_id']
            channel_id = scrim.get('channel_id')
            
            # 참가자 목록 조회
            participants = await self.bot.db_manager.get_participants(scrim_id)
            joined_users = [p for p in participants if p['status'] == 'joined']
            
            if not joined_users or not channel_id:
                return
            
            # 길드 및 채널 가져오기
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                logger.warning(f"⚠️ 길드를 찾을 수 없음: {guild_id}")
                return
                
            channel = guild.get_channel(int(channel_id))
            if not channel:
                logger.warning(f"⚠️ 채널을 찾을 수 없음: {channel_id}")
                return
            
            # 마감 알림 메시지 생성
            scrim_date_str = datetime.fromisoformat(scrim['scrim_date']).strftime('%Y년 %m월 %d일 %H:%M')
            participant_mentions = ', '.join([f"<@{p['user_id']}>" for p in joined_users[:10]]) 
            
            embed = discord.Embed(
                title="🎯 길드 간 스크림 모집 마감",
                description=f"**{scrim['title']}** 모집이 자동으로 마감되었습니다.",
                color=0xff9900
            )
            
            embed.add_field(
                name="📅 스크림 일시",
                value=scrim_date_str,
                inline=True
            )
            
            embed.add_field(
                name="🎯 티어대", 
                value=scrim['tier_range'],
                inline=True
            )
            
            embed.add_field(
                name="👥 최종 참가자",
                value=f"{len(joined_users)}명 확정",
                inline=True
            )
            
            if scrim.get('opponent_team'):
                embed.add_field(
                    name="⚔️ 상대팀",
                    value=scrim['opponent_team'],
                    inline=False
                )
            
            if joined_users:
                embed.add_field(
                    name="📢 참가자 알림",
                    value=f"{participant_mentions}\n\n스크림 시작 전 준비 바랍니다!",
                    inline=False
                )
            
            embed.set_footer(text=f"모집 ID: {scrim_id}")
            
            # 알림 메시지 전송
            await channel.send(embed=embed)
            logger.info(f"📢 길드 간 스크림 마감 알림 전송: {scrim['title']}")
            
        except Exception as e:
            logger.error(f"🚨 길드 간 스크림 마감 알림 전송 실패: {e}")
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """스케줄러 상태 정보 반환"""
        try:
            # 활성 스크림 수 조회 (모든 길드)
            total_active = 0
            expired_count = 0
            
            try:
                expired_scrims = await self.bot.db_manager.get_expired_scrims()
                expired_count = len(expired_scrims)
                
                # 간단한 통계 조회 (첫 번째 길드만 예시)
                guilds = [guild.id for guild in self.bot.guilds]
                if guilds:
                    first_guild_scrims = await self.bot.db_manager.get_active_scrims(str(guilds[0]))
                    total_active = len(first_guild_scrims)
                    
            except Exception as e:
                logger.warning(f"⚠️ 스케줄러 상태 조회 중 오류: {e}")
            
            return {
                'running': self.running,
                'total_active_scrims': total_active,
                'expired_scrims_pending': expired_count,
                'last_check': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"🚨 스케줄러 상태 조회 오류: {e}")
            return {
                'running': self.running,
                'error': str(e),
                'last_check': datetime.now(timezone.utc).isoformat()
            }