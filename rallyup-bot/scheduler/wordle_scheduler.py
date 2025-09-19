import asyncio
import aiosqlite
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
import logging

import discord

from config.settings import Settings

if TYPE_CHECKING:
    from main import RallyUpBot

logger = logging.getLogger(__name__)

class WordleScheduler:
    def __init__(self, bot: 'RallyUpBot'):
        self.bot = bot
        self.is_running = False
        self._task = None
    
    async def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("🎯 띵지워들 스케줄러가 시작되었습니다.")
    
    async def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("🎯 띵지워들 스케줄러가 중지되었습니다.")
    
    async def _scheduler_loop(self):
        """메인 스케줄러 루프"""
        logger.info("🔄 띵지워들 스케줄러 루프 시작")
        
        while self.is_running:
            try:
                # 게임 만료 처리 (1분마다)
                await self._process_expired_games()
                
                # 출제자 보상 지급 처리 (1분마다)
                await self._process_creator_rewards()
                
                # 포인트 풀 정리 (5분마다)
                await self._cleanup_completed_games()
                
                # 60초 대기
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                logger.info("🛑 띵지워들 스케줄러 루프가 취소되었습니다.")
                break
            except Exception as e:
                logger.error(f"🚨 띵지워들 스케줄러 오류: {e}")
                # 오류 발생 시 5분 대기 후 재시도
                await asyncio.sleep(300)
    
    async def _process_creator_rewards(self):
        """완료된 게임의 출제자 보상 처리"""
        try:
            completed_games = await self._get_reward_pending_games()
            
            for game in completed_games:
                await self._process_single_creator_reward(game)
            
            if completed_games:
                logger.info(f"💰 {len(completed_games)}개 게임의 출제자 보상을 처리했습니다.")
                
        except Exception as e:
            logger.error(f"🚨 출제자 보상 처리 중 오류: {e}")
    
    async def _get_reward_pending_games(self):
        """보상 지급 대기 중인 게임들 조회"""
        try:
            async with aiosqlite.connect(Settings.DATABASE_PATH) as db:
                # 완료된 게임 중 24시간이 지난 게임들
                async with db.execute('''
                    SELECT DISTINCT wg.id, wg.creator_id, wg.creator_username
                    FROM wordle_games wg
                    WHERE wg.is_completed = 1 
                      AND wg.completed_at <= datetime('now', '-24 hours')
                      AND (wg.creator_reward_paid IS NULL OR wg.creator_reward_paid != 1)
                    ORDER BY wg.completed_at ASC
                    LIMIT 10
                ''') as cursor:
                    rows = await cursor.fetchall()
                    
                    return [
                        {
                            'id': row[0],
                            'creator_id': row[1],
                            'creator_username': row[2]
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"보상 대기 게임 조회 실패: {e}")
            return []
    
    async def _process_single_creator_reward(self, game: dict):
        """개별 출제자 보상 처리"""
        try:
            guild_id = game.get('guild_id')
            game_id = game['id']
            creator_id = game['creator_id']
            
            if await self._is_reward_already_paid(game_id):
                logger.debug(f"게임 #{game_id}은 이미 보상 처리 완료됨")
                return True
            
            reward = await self.bot.db_manager.calculate_creator_reward(game_id)
            success = await self._atomic_reward_payment(guild_id, creator_id, game_id, reward)

            if success:
                logger.info(f"💎 게임 #{game_id} 출제자 보상 지급: {reward}점")
                # 출제자에게 알림 DM 발송
                await self._send_creator_reward_notification(creator_id, game_id, reward)
            
            return success
            
        except Exception as e:
            logger.error(f"🚨 게임 #{game.get('id', 'Unknown')} 출제자 보상 처리 오류: {e}")
            return False
        
    async def _is_reward_already_paid(self, game_id: int) -> bool:
        """보상이 이미 지급되었는지 확인"""
        try:
            async with aiosqlite.connect(Settings.DATABASE_PATH) as db:
                async with db.execute('SELECT creator_reward_paid FROM wordle_games WHERE id = ?', 
                                    (game_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result and result[0] == 1
        except Exception:
            return False

    async def _atomic_reward_payment(self, guild_id: str, creator_id: str, game_id: int, reward: int) -> bool:
        """원자적 보상 지급 처리"""
        try:
            async with aiosqlite.connect(Settings.DATABASE_PATH) as db:
                await db.execute('BEGIN IMMEDIATE')
                
                try:
                    # 1. 다시 한번 중복 체크 (동시성 방지)
                    async with db.execute('SELECT creator_reward_paid FROM wordle_games WHERE id = ?', 
                                        (game_id,)) as cursor:
                        result = await cursor.fetchone()
                        if result and result[0] == 1:
                            await db.execute('ROLLBACK')
                            return True
                    
                    # 2. 포인트 지급
                    await db.execute('''
                        UPDATE users 
                        SET wordle_points = wordle_points + ?, updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ? AND discord_id = ?
                    ''', (reward, guild_id, creator_id))
                    
                    # 3. 플래그 설정
                    await db.execute('''
                        UPDATE wordle_games 
                        SET creator_reward_paid = 1, reward_processed_at = datetime('now')
                        WHERE id = ?
                    ''', (game_id,))
                    
                    await db.commit()
                    return True
                    
                except Exception as e:
                    await db.execute('ROLLBACK')
                    logger.error(f"보상 지급 트랜잭션 실패: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"원자적 보상 처리 실패: {e}")
            return False

    async def _send_creator_reward_notification(self, creator_id: str, game_id: int, reward: int):
        """출제자에게 보상 알림 DM 발송"""
        try:
            user = await self.bot.fetch_user(int(creator_id))
            if user:
                import discord
                
                embed = discord.Embed(
                    title="💎 띵지워들 출제자 보상",
                    description=f"게임 #{game_id}에 대한 출제자 보상이 지급되었습니다!",
                    color=0xffd700,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="💰 보상 포인트",
                    value=f"**{reward:,}점**이 지급되었습니다!",
                    inline=False
                )
                
                if reward >= 200:
                    embed.add_field(
                        name="🎉 적절한 난이도!",
                        value="플레이어들이 이 게임의 난이도를 '적절함'으로 평가했습니다.\n"
                              "좋은 문제를 출제해주셔서 감사합니다!",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="📝 참여 보상",
                        value="게임 참여에 대한 기본 보상입니다.\n"
                              "다음에는 더 적절한 난이도로 도전해보세요!",
                        inline=False
                    )
                
                embed.set_footer(text="띵지워들 게임 시스템")
                
                await user.send(embed=embed)
                
        except Exception as e:
            logger.debug(f"출제자 보상 DM 발송 실패 (user_id: {creator_id}): {e}")
    
    async def _process_expired_games(self):
        """만료된 게임들 처리"""
        try:
            expired_games = await self.bot.db_manager.get_expired_games()
            
            for game in expired_games:
                await self._handle_expired_game(game)
                
            if expired_games:
                logger.info(f"🕐 {len(expired_games)}개의 만료된 게임을 처리했습니다.")
                
        except Exception as e:
            logger.error(f"🚨 만료 게임 처리 중 오류: {e}")
    
    async def _handle_expired_game(self, game: dict):
        """개별 만료 게임 처리"""
        try:
            game_id = game['id']
            creator_id = game['creator_id']
            total_pool = game['total_pool']
            
            # 게임 만료 처리
            await self.bot.db_manager.expire_game(game_id)

            # 출제자에게 포인트 반환
            await self.bot.db_manager.add_user_points(creator_id, total_pool)

            logger.info(f"⏰ 게임 #{game_id} 만료 처리 완료 - {total_pool:,}점 반환")
            
            # 출제자에게 DM 알림 (선택사항)
            await self._send_expiry_notification(creator_id, game_id, total_pool)
            
        except Exception as e:
            logger.error(f"🚨 게임 #{game.get('id', 'Unknown')} 만료 처리 오류: {e}")
    
    async def _send_expiry_notification(self, creator_id: str, game_id: int, points: int):
        """출제자에게 만료 알림 DM 발송"""
        try:
            user = await self.bot.fetch_user(int(creator_id))
            if user:
                embed = discord.Embed(
                    title="⏰ 띵지워들 게임 만료 알림",
                    description=f"등록하신 게임 #{game_id}이 24시간 만료되어 자동으로 종료되었습니다.",
                    color=0x95a5a6,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="💰 포인트 반환",
                    value=f"**{points:,}점**이 계정으로 반환되었습니다.\n"
                          f"(베팅 포인트 + 도전자들의 실패 포인트)",
                    inline=False
                )
                
                embed.add_field(
                    name="🎯 다음 게임",
                    value="`/띵지워들 등록`으로 새로운 게임을 등록해보세요!",
                    inline=False
                )
                
                embed.set_footer(text="띵지워들 게임 시스템")
                
                await user.send(embed=embed)
                
        except Exception as e:
            # DM 발송 실패는 로그만 남기고 넘어감
            logger.debug(f"DM 발송 실패 (user_id: {creator_id}): {e}")
    
    async def _cleanup_completed_games(self):
        """완료된 게임들의 데이터 정리"""
        try:
            # 30일 이상 된 완료 게임들의 추측 로그 정리 등
            # 현재는 간단한 로그만 출력
            # 실제로는 오래된 데이터 정리 로직을 추가할 수 있음
            
            current_time = datetime.now()
            logger.debug(f"🧹 게임 데이터 정리 검사 완료 ({current_time.strftime('%H:%M')})")
            
        except Exception as e:
            logger.error(f"🚨 게임 데이터 정리 중 오류: {e}")
    
    async def force_expire_game(self, game_id: int) -> bool:
        """특정 게임 강제 만료 (관리자용)"""
        try:
            game = await self.bot.db_manager.get_game_by_id(game_id)
            if not game or game['is_completed']:
                return False
            
            await self._handle_expired_game({
                'id': game_id,
                'creator_id': game['creator_id'],
                'total_pool': game['total_pool']
            })
            
            return True
            
        except Exception as e:
            logger.error(f"🚨 게임 #{game_id} 강제 만료 실패: {e}")
            return False
    
    async def get_scheduler_status(self) -> dict:
        """스케줄러 상태 조회"""
        return {
            'is_running': self.is_running,
            'task_status': 'running' if self._task and not self._task.done() else 'stopped',
            'last_check': datetime.now().isoformat()
        }