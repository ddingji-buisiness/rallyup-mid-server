from dataclasses import dataclass
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import edge_tts
import asyncio
import os
import tempfile
import time
import logging
import glob
import platform
from typing import Optional, Dict, Any, Literal

logger = logging.getLogger(__name__)

@dataclass
class VoiceChannelSession:
    """채널별 TTS 세션 관리 클래스"""
    voice_client: discord.VoiceClient
    channel: discord.VoiceChannel
    guild_id: str
    queue: asyncio.Queue
    processor_task: asyncio.Task
    created_at: float
    log_thread: Optional[discord.Thread] = None

    def __post_init__(self):
        """세션 생성 시 로그"""
        logger.info(f"🆕 TTS 세션 생성: {self.channel.name} (ID: {self.channel.id})")
    
    @property
    def channel_id(self) -> str:
        return str(self.channel.id)
    
    def is_active(self) -> bool:
        """세션이 활성 상태인지 확인"""
        return (
            self.voice_client.is_connected() and 
            not self.processor_task.done()
        )
        
class TTSCommands(commands.Cog):
    """Linux 서버용 TTS Commands (Opus 경로 수정)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.sessions: Dict[str, VoiceChannelSession] = {}
        self.voice_clients: Dict[str, discord.VoiceClient] = {}
        self.tts_settings: Dict[str, Dict[str, Any]] = {}
        self.tts_queues: Dict[str, asyncio.Queue] = {} 
        self.queue_processors: Dict[str, asyncio.Task] = {} 
        self.tts_threads: Dict[str, discord.Thread] = {}
        self.daily_threads_cache: Dict[str, discord.Thread] = {}
        self.session_message_counts: Dict[str, int] = {}

        self.korean_voices = {
            '인준': {
                'voice': 'ko-KR-InJoonNeural',
                'name': '인준 (남성, 친근한)',
                'gender': '남성',
                'style': '친근한',
                'language': 'ko-KR'
            },
            '선희': {
                'voice': 'ko-KR-SunHiNeural', 
                'name': '선희 (여성, 밝은)',
                'gender': '여성',
                'style': '밝은',
                'language': 'ko-KR'
            },
            '현수': {
                'voice': 'ko-KR-HyunsuNeural',
                'name': '현수 (남성, 차분한)',
                'gender': '남성', 
                'style': '차분한',
                'language': 'ko-KR'
            },
            '국민': {
                'voice': 'ko-KR-GookMinNeural',
                'name': '국민 (남성, 표준어)',
                'gender': '남성',
                'style': '표준어',
                'language': 'ko-KR'
            },
            '봉진': {
                'voice': 'ko-KR-BongJinNeural',
                'name': '봉진 (남성, 중후한)',
                'gender': '남성',
                'style': '중후한',
                'language': 'ko-KR'
            },
            '지민': {
                'voice': 'ko-KR-JiMinNeural',
                'name': '지민 (여성, 활발한)',
                'gender': '여성',
                'style': '활발한',
                'language': 'ko-KR'
            },
            '서현': {
                'voice': 'ko-KR-SeoHyeonNeural',
                'name': '서현 (여성, 차분한)',
                'gender': '여성',
                'style': '차분한',
                'language': 'ko-KR'
            },
            '순복': {
                'voice': 'ko-KR-SoonBokNeural',
                'name': '순복 (여성, 따뜻한)',
                'gender': '여성',
                'style': '따뜻한',
                'language': 'ko-KR'
            },
            '유진': {
                'voice': 'ko-KR-YuJinNeural',
                'name': '유진 (여성, 부드러운)',
                'gender': '여성',
                'style': '부드러운',
                'language': 'ko-KR'
            }
        }

        self.english_voices = {
            'Guy': {
                'voice': 'en-US-GuyNeural',
                'name': 'Guy (미국 남성, 친근)',
                'gender': '남성',
                'style': '친근한',
                'language': 'en-US'
            },
            'Jenny': {
                'voice': 'en-US-JennyNeural',
                'name': 'Jenny (미국 여성, 명료)',
                'gender': '여성',
                'style': '명료한',
                'language': 'en-US'
            },
            'Aria': {
                'voice': 'en-US-AriaNeural',
                'name': 'Aria (미국 여성, 뉴스)',
                'gender': '여성',
                'style': '뉴스 스타일',
                'language': 'en-US'
            },
            'William': {
                'voice': 'en-AU-WilliamNeural',
                'name': 'William (호주 남성)',
                'gender': '남성',
                'style': '호주식',
                'language': 'en-AU'
            }
        }

        self.spanish_voices = {
            'Alvaro': {
                'voice': 'es-ES-AlvaroNeural',
                'name': 'Álvaro (스페인 남성)',
                'gender': '남성',
                'style': '표준',
                'language': 'es-ES'
            },
            'Elvira': {
                'voice': 'es-ES-ElviraNeural',
                'name': 'Elvira (스페인 여성)',
                'gender': '여성',
                'style': '부드러운',
                'language': 'es-ES'
            },
            'Jorge': {
                'voice': 'es-MX-JorgeNeural',
                'name': 'Jorge (멕시코 남성)',
                'gender': '남성',
                'style': '친근한',
                'language': 'es-MX'
            },
            'Dalia': {
                'voice': 'es-MX-DaliaNeural',
                'name': 'Dalia (멕시코 여성)',
                'gender': '여성',
                'style': '명랑한',
                'language': 'es-MX'
            }
        }

        self.chinese_voices = {
            'Yunxi': {
                'voice': 'zh-CN-YunxiNeural',
                'name': '云希 Yunxi (중국 남성)',
                'gender': '남성',
                'style': '친근한',
                'language': 'zh-CN'
            },
            'Xiaoxiao': {
                'voice': 'zh-CN-XiaoxiaoNeural',
                'name': '晓晓 Xiaoxiao (중국 여성)',
                'gender': '여성',
                'style': '밝은',
                'language': 'zh-CN'
            },
            'Yunyang': {
                'voice': 'zh-CN-YunyangNeural',
                'name': '云扬 Yunyang (중국 남성, 뉴스)',
                'gender': '남성',
                'style': '뉴스 스타일',
                'language': 'zh-CN'
            },
            'Xiaoyi': {
                'voice': 'zh-CN-XiaoyiNeural',
                'name': '晓伊 Xiaoyi (중국 여성)',
                'gender': '여성',
                'style': '차분한',
                'language': 'zh-CN'
            },
            'YunJhe': {
                'voice': 'zh-TW-YunJheNeural',
                'name': '雲哲 YunJhe (대만 남성)',
                'gender': '남성',
                'style': '표준',
                'language': 'zh-TW'
            },
            'HsiaoChen': {
                'voice': 'zh-TW-HsiaoChenNeural',
                'name': '曉臻 HsiaoChen (대만 여성)',
                'gender': '여성',
                'style': '부드러운',
                'language': 'zh-TW'
            },
            'WanLung': {
                'voice': 'zh-HK-WanLungNeural',
                'name': '雲龍 WanLung (홍콩 남성)',
                'gender': '남성',
                'style': '친근한',
                'language': 'zh-HK'
            },
            'HiuMaan': {
                'voice': 'zh-HK-HiuMaanNeural',
                'name': '曉曼 HiuMaan (홍콩 여성)',
                'gender': '여성',
                'style': '밝은',
                'language': 'zh-HK'
            }
        }

        self.all_voices = {
            **self.korean_voices, 
            **self.english_voices,
            **self.spanish_voices,
            **self.chinese_voices
        }

        self.ffmpeg_executable = self._find_ffmpeg()
        self._force_load_opus_linux()

    def _find_ffmpeg(self):
        """FFmpeg 경로 찾기 (Linux 서버용)"""
        paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',
            'ffmpeg'
        ]
        
        for path in paths:
            if path == 'ffmpeg' or os.path.exists(path):
                logger.info(f"✅ FFmpeg 경로: {path}")
                return path
        
        logger.warning("⚠️ FFmpeg를 찾을 수 없음")
        return 'ffmpeg'

    def _force_load_opus_linux(self):
        """Linux 서버용 Opus 강제 로딩"""
        try:
            import discord.opus
            
            if discord.opus.is_loaded():
                logger.info("✅ Opus가 이미 로드되어 있음")
                return True
            
            logger.info("🔊 Linux 서버용 Opus 라이브러리 로딩 중...")
            
            # 운영체제별 경로 설정
            system = platform.system().lower()
            
            if system == 'linux':
                # Linux 서버용 Opus 경로들
                opus_search_patterns = [
                    '/usr/lib/x86_64-linux-gnu/libopus.so*',
                    '/usr/lib/aarch64-linux-gnu/libopus.so*',
                    '/usr/lib/arm-linux-gnueabihf/libopus.so*',
                    '/usr/lib64/libopus.so*',
                    '/usr/lib/libopus.so*',
                    '/usr/local/lib/libopus.so*',
                    '/lib/x86_64-linux-gnu/libopus.so*',
                ]
                
                # 간단한 이름들 (Linux)
                simple_names = ['opus', 'libopus.so.0', 'libopus.so', 'libopus']
                
            elif system == 'darwin':
                # macOS용 경로들 (호환성)
                opus_search_patterns = [
                    '/opt/homebrew/Cellar/opus/*/lib/libopus.*.dylib',
                    '/opt/homebrew/lib/libopus.*.dylib',
                    '/usr/local/lib/libopus.*.dylib',
                ]
                
                simple_names = ['opus', 'libopus.dylib', 'libopus.0.dylib']
                
            else:
                # Windows나 기타 시스템
                opus_search_patterns = []
                simple_names = ['opus', 'libopus']
            
            # glob으로 실제 파일 찾기
            found_opus_files = []
            for pattern in opus_search_patterns:
                matches = glob.glob(pattern)
                found_opus_files.extend(matches)
            
            # 중복 제거 및 정렬 (최신 버전 우선)
            found_opus_files = sorted(list(set(found_opus_files)), reverse=True)
            
            logger.info(f"🔍 발견된 Opus 파일들: {found_opus_files}")
            
            # 각 파일에 대해 로딩 시도
            for opus_file in found_opus_files:
                if os.path.exists(opus_file) and os.access(opus_file, os.R_OK):
                    try:
                        logger.info(f"🔊 Opus 로딩 시도: {opus_file}")
                        discord.opus.load_opus(opus_file)
                        
                        if discord.opus.is_loaded():
                            logger.info(f"✅ Opus 로딩 성공: {opus_file}")
                            return True
                        else:
                            logger.debug(f"⚠️ 로딩했지만 확인 실패: {opus_file}")
                            
                    except Exception as e:
                        logger.debug(f"❌ Opus 로딩 실패 ({opus_file}): {e}")
                        continue
                else:
                    logger.debug(f"⚠️ 접근 불가: {opus_file}")
            
            # 간단한 이름으로 시도
            logger.info("🔊 간단한 이름으로 Opus 로딩 시도...")
            for name in simple_names:
                try:
                    logger.info(f"🔊 시도: {name}")
                    discord.opus.load_opus(name)
                    
                    if discord.opus.is_loaded():
                        logger.info(f"✅ Opus 로딩 성공 (간단한 이름): {name}")
                        return True
                        
                except Exception as e:
                    logger.debug(f"❌ 간단한 이름 로딩 실패 ({name}): {e}")
                    continue
            
            # 모든 시도 실패
            logger.error("❌ 모든 Opus 로딩 시도 실패!")
            logger.error("💡 해결 방법:")
            logger.error("1. sudo apt install libopus-dev")
            logger.error("2. pip install 'discord.py[voice]' --force-reinstall")
            logger.error("3. pip install PyNaCl --force-reinstall")
            
            return False
            
        except ImportError as e:
            logger.error(f"❌ discord.opus 모듈 임포트 실패: {e}")
            logger.error("💡 해결: pip install 'discord.py[voice]'")
            return False
        except Exception as e:
            logger.error(f"❌ Opus 로딩 중 예상치 못한 오류: {e}", exc_info=True)
            return False
        
    tts_setup = app_commands.Group(name="tts설정", description="TTS 시스템 설정")

    @tts_setup.command(name="로그채널", description="TTS 대화 기록을 저장할 채널을 설정합니다")
    @app_commands.describe(채널="TTS 로그를 기록할 텍스트 채널")
    @app_commands.default_permissions(manage_guild=True)
    async def set_log_channel(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        """TTS 로그 채널 설정"""
        guild_id = str(interaction.guild.id)
        channel_id = str(채널.id)
        
        try:
            # 봇 권한 확인
            bot_permissions = 채널.permissions_for(interaction.guild.me)
            required_permissions = [
                bot_permissions.send_messages,
                bot_permissions.create_public_threads,
                bot_permissions.send_messages_in_threads
            ]
            
            if not all(required_permissions):
                embed = discord.Embed(
                    title="⛔ 권한 부족",
                    description=f"{채널.mention}에 필요한 권한이 없습니다.",
                    color=0xff0000
                )
                embed.add_field(
                    name="필요한 권한",
                    value="• 메시지 보내기\n• 공개 쓰레드 만들기\n• 쓰레드에서 메시지 보내기",
                    inline=False
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # DB에 저장
            async with self.bot.db_manager.get_connection() as db:
                await db.execute('''
                    INSERT INTO tts_log_settings (guild_id, log_channel_id, enabled, updated_at)
                    VALUES (?, ?, TRUE, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        log_channel_id = excluded.log_channel_id,
                        enabled = TRUE,
                        updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, channel_id))
                await db.commit()
            
            embed = discord.Embed(
                title="✅ TTS 로그 채널 설정 완료",
                description=f"{채널.mention}에 TTS 대화 기록이 저장됩니다.",
                color=0x00ff00
            )
            embed.add_field(
                name="📝 동작 방식",
                value="• 첫 TTS 사용 시 자동으로 쓰레드 생성\n"
                      "• 음성 채널별로 별도 쓰레드 관리\n"
                      "• 모든 대화 내역 실시간 기록",
                inline=False
            )
            embed.set_footer(text="이제 /말하기 명령어를 사용해보세요!")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"✅ TTS 로그 채널 설정: {interaction.guild.name} -> #{채널.name}")
            
        except Exception as e:
            embed = discord.Embed(
                title="⛔ 설정 실패",
                description=f"오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.error(f"⛔ TTS 로그 채널 설정 오류: {e}", exc_info=True)

    @tts_setup.command(name="상태", description="현재 TTS 로그 설정을 확인합니다")
    async def log_status(self, interaction: discord.Interaction):
        """TTS 로그 설정 상태 확인"""
        guild_id = str(interaction.guild.id)
        
        try:
            # DB에서 설정 조회
            async with self.bot.db_manager.get_connection() as db:
                cursor = await db.execute(
                    'SELECT log_channel_id, enabled FROM tts_log_settings WHERE guild_id = ?',
                    (guild_id,)
                )
                result = await cursor.fetchone()
            
            embed = discord.Embed(
                title="📊 TTS 로그 설정 상태",
                color=0x0099ff
            )
            
            if result and result[0]:
                channel_id, enabled = result
                channel = interaction.guild.get_channel(int(channel_id))
                
                if channel:
                    status_emoji = "✅" if enabled else "⛔"
                    embed.add_field(
                        name=f"{status_emoji} 로그 채널",
                        value=f"{channel.mention}",
                        inline=False
                    )
                    
                    # 활성 쓰레드 확인
                    active_threads = [
                        thread for channel_id, thread in self.tts_threads.items()
                        if thread.guild.id == interaction.guild.id
                    ]
                    
                    if active_threads:
                        thread_list = "\n".join([f"• {t.name}" for t in active_threads[:5]])
                        embed.add_field(
                            name=f"🧵 활성 쓰레드 ({len(active_threads)}개)",
                            value=thread_list + (f"\n... 외 {len(active_threads)-5}개" if len(active_threads) > 5 else ""),
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="⚠️ 로그 채널",
                        value="설정된 채널을 찾을 수 없습니다.\n다시 설정해주세요.",
                        inline=False
                    )
            else:
                embed.description = "로그 채널이 설정되지 않았습니다."
                embed.add_field(
                    name="💡 설정 방법",
                    value="`/tts설정 로그채널 #채널이름`",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(
                f"⛔ 설정 조회 중 오류 발생: {str(e)}", 
                ephemeral=True
            )
            logger.error(f"⛔ TTS 설정 조회 오류: {e}", exc_info=True)

    @app_commands.command(name="입장", description="TTS 봇을 음성 채널에 입장시킵니다")
    async def tts_join(self, interaction: discord.Interaction):
        """TTS 봇 음성 채널 입장"""
        try:
            import discord.opus
            if not discord.opus.is_loaded():
                # 다시 한번 로딩 시도
                self._force_load_opus_linux()
                
                if not discord.opus.is_loaded():
                    embed = discord.Embed(
                        title="❌ 음성 라이브러리 오류",
                        description="Opus 라이브러리를 로드할 수 없습니다.",
                        color=0xff0000
                    )
                    embed.add_field(
                        name="🔧 서버 관리자 해결 방법",
                        value="```bash\n"
                              "# 1. Opus 개발 라이브러리 설치\n"
                              "sudo apt install libopus-dev\n\n"
                              "# 2. Discord.py 재설치\n"
                              "pip install 'discord.py[voice]' --force-reinstall\n"
                              "```",
                        inline=False
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
        except ImportError:
            embed = discord.Embed(
                title="❌ Discord.py 음성 모듈 오류",
                description="Discord.py가 음성 지원 없이 설치되었습니다.",
                color=0xff0000
            )
            embed.add_field(
                name="🔧 해결 방법",
                value="`pip install 'discord.py[voice]'`를 실행해주세요",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not interaction.user.voice:
            embed = discord.Embed(
                title="⌛ 음성 채널 필요",
                description="먼저 음성 채널에 입장한 후 명령어를 사용해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        channel = interaction.user.voice.channel
        channel_id = str(channel.id)
        guild_id = str(interaction.guild.id)
        
        try:
            # 이미 해당 채널에 연결되어 있는지 확인
            if channel_id in self.voice_clients and self.voice_clients[channel_id].is_connected():
                embed = discord.Embed(
                    title="ℹ️ 이미 연결됨",
                    description=f"이미 **{channel.name}**에 연결되어 있습니다!",
                    color=0x0099ff
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            existing_channel_id = None
            existing_channel_name = None
            for ch_id, vc in self.voice_clients.items():
                if vc.is_connected() and str(vc.guild.id) == guild_id:
                    existing_channel_id = ch_id
                    existing_channel_name = vc.channel.name
                    break
            
            # 같은 서버의 다른 채널에 이미 연결되어 있으면
            if existing_channel_id and existing_channel_id != channel_id:
                # 기존 채널 정리
                await self._cleanup_channel(existing_channel_id)
                
                # 사용자에게 이동 안내
                await interaction.response.defer()
                
                move_embed = discord.Embed(
                    title="🔄 채널 이동",
                    description=f"**{existing_channel_name}**에서 **{channel.name}**으로 이동합니다...",
                    color=0xffa500
                )
                await interaction.followup.send(embed=move_embed, ephemeral=True)
                
                # 잠시 대기 (정리 완료 대기)
                await asyncio.sleep(1)
            else:
                await interaction.response.defer()
            
            # 같은 채널이지만 연결이 끊긴 경우 정리
            if channel_id in self.voice_clients:
                old_vc = self.voice_clients[channel_id]
                if not old_vc.is_connected():
                    await self._cleanup_channel(channel_id)
                        
            # 음성 채널 연결
            voice_client = await channel.connect(timeout=10.0, reconnect=True)
            self.voice_clients[channel_id] = voice_client

            # 큐 초기화 및 프로세서 시작
            self.tts_queues[channel_id] = asyncio.Queue()
            self.queue_processors[channel_id] = asyncio.create_task(
                self._process_tts_queue(channel_id)
            )

            self.session_message_counts[channel_id] = 0

            logger.info(f"🎵 TTS 큐 프로세서 시작: {interaction.guild.name}")
            
            # 기본 설정 초기화
            if guild_id not in self.tts_settings:
                self.tts_settings[guild_id] = {
                    'voice': '인준',
                    'rate': '+0%',
                    'pitch': '+0Hz',
                    'volume': '+0%',
                    'last_used': time.time()
                }
                logger.info(f"🆕 새 서버 TTS 설정 초기화: {interaction.guild.name}")
            else:
                self.tts_settings[guild_id]['last_used'] = time.time()

            await self._log_session_start(guild_id, channel.name, interaction.user)
            
            # 연결 안정화 대기
            await asyncio.sleep(0.5)
            
            if not voice_client.is_connected():
                await interaction.followup.send("⌛ 음성 연결에 실패했습니다.")
                return
            
            # 성공 메시지
            current_voice = self.tts_settings[guild_id]['voice']
            voice_info = self.korean_voices[current_voice]
            connected_channels = self._get_guild_connected_channels(guild_id)
            
            embed = discord.Embed(
                title="🎤 TTS 봇 입장 완료",
                description=f"**{channel.name}**에 입장했습니다!",
                color=0x00ff00
            )
            
            # embed.add_field(
            #     name="🔧 시스템 상태",
            #     value=f"🎵 Edge TTS: ✅ 정상\n"
            #         f"⚙️ Opus: ✅ 로드됨\n"
            #         f"🖥️ 서버: Linux\n"
            #         f"📶 지연시간: {voice_client.latency*1000:.1f}ms\n"
            #         f"🎭 현재 목소리: {voice_info['name']}\n"
            #         f"📋 큐 시스템: ✅ 활성화\n"
            #         f"🔀 활성 채널: {len(connected_channels)}개\n"
            #         f"📝 기록 시스템: ✅ 활성화",
            #     inline=False
            # )
            
            embed.add_field(
                name="📖 사용법",
                value="`/말하기 <내용> [목소리]` - 텍스트를 음성으로 변환\n"
                    "`/대기열` - 현재 대기 중인 TTS 확인\n"
                    "`/볼륨설정 <속도> [피치]` - 목소리 설정 조절\n"
                    "`/현재볼륨` - 현재 설정 확인\n"
                    "`/퇴장` - 현재 채널에서 퇴장",
                inline=False
            )
            
            embed.set_footer(text="💡 첫 TTS 사용 시 자동으로 대화 기록 쓰레드가 생성됩니다!")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"🎤 TTS 봇 입장: {interaction.guild.name} > {channel.name}")
            
        except Exception as e:
            embed = discord.Embed(
                title="⌛ 입장 실패",
                description=f"예상치 못한 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"⌛ TTS 입장 오류: {e}", exc_info=True)

    @app_commands.command(name="말하기", description="텍스트를 음성으로 변환하여 재생합니다")
    @app_commands.describe(
        내용="음성으로 변환할 텍스트 (1-1000자)",
        목소리="사용할 목소리 선택 (기본값: 서버 설정)"
    )
    async def tts_speak(
        self, 
        interaction: discord.Interaction, 
        내용: str,
        목소리: Optional[Literal[
            '인준', '선희', '현수', '국민', '봉진', '지민', '서현', '순복', '유진',
            'Guy', 'Jenny', 'Aria', 'William',
            'Alvaro', 'Elvira', 'Jorge', 'Dalia',
            'Yunxi', 'Xiaoxiao', 'Yunyang', 'Xiaoyi', 
            'YunJhe', 'HsiaoChen', 'WanLung', 'HiuMaan'
        ]] = None
    ):
        guild_id = str(interaction.guild.id)
        
        # 입력 검증
        if not 내용 or len(내용.strip()) == 0:
            await interaction.response.send_message("❌ 텍스트를 입력해주세요!", ephemeral=True)
            return
            
        if len(내용) > 1000:
            await interaction.response.send_message("❌ 텍스트는 1000자 이하로 입력해주세요!", ephemeral=True)
            return
        
        if not interaction.user.voice:
            await interaction.response.send_message(
                "⏸️ 음성 채널에 입장한 후 명령어를 사용해주세요!",
                ephemeral=True
            )
            return
        
        user_channel = interaction.user.voice.channel
        channel_id = str(user_channel.id)
        
        # 해당 채널에 봇이 연결되어 있는지 확인
        if channel_id not in self.voice_clients:
            await interaction.response.send_message(
                f"⏸️ **{user_channel.name}**에 봇이 없습니다!\n"
                f"먼저 `/입장` 명령어를 사용해주세요.",
                ephemeral=True
            )
            return
            
        voice_client = self.voice_clients[channel_id]
        if not voice_client.is_connected():
            await interaction.response.send_message(
                f"⏸️ **{user_channel.name}**의 음성 연결이 끊어졌습니다.\n"
                f"`/입장`을 다시 해주세요!",
                ephemeral=True
            )
            return
        
        # 목소리 결정 (우선순위: 명령어 > 개인설정 > 서버기본)
        selected_voice = 목소리
        if not selected_voice:
            # 개인 설정 조회
            user_id = str(interaction.user.id)
            preference = await self.bot.db_manager.get_user_tts_preference(guild_id, user_id)
            if preference:
                selected_voice = preference['voice']
            else:
                selected_voice = self.tts_settings.get(guild_id, {}).get('voice', '인준')
        
        voice_info = self.all_voices.get(selected_voice)
        if not voice_info:
            await interaction.response.send_message("⛔ 올바르지 않은 목소리입니다!", ephemeral=True)
            return

        # 큐에 추가
        tts_request = {
            'user': interaction.user,
            'user_id': str(interaction.user.id),
            'text': 내용,
            'voice': selected_voice,
            'timestamp': time.time(),
            'channel_name': user_channel.name,
            'channel_id': channel_id,
            'auto_tts': False  # 명령어 사용
        }

        await self.tts_queues[channel_id].put(tts_request)
        queue_size = self.tts_queues[channel_id].qsize()

        lang = voice_info.get('language', 'ko-KR')
        language_emoji = (
            "🇰🇷" if 'ko' in lang.lower()
            else "🇪🇸" if 'es' in lang.lower()
            else "🇨🇳" if 'zh' in lang.lower()
            else "🇺🇸" if 'US' in lang 
            else "🇬🇧" if 'GB' in lang 
            else "🇦🇺" if 'AU' in lang
            else "🌐"
        )
        
        # 1. 명령어 사용자에게는 간단한 확인 메시지 (ephemeral)
        if queue_size == 1:
            await interaction.response.send_message(
                f"🎵 재생 중...",
                ephemeral=True,
                delete_after=2
            )
        else:
            await interaction.response.send_message(
                f"📋 대기열 {queue_size}번째에 추가되었습니다!",
                ephemeral=True
            )

        if await self._can_send_in_channel(text_channel):
            # 메시지 전송
            pass
        else:
            logger.warning(f"⚠️ 채널 권한 부족: {text_channel.name}")

        text_channel = interaction.channel

        if isinstance(text_channel, discord.TextChannel):
            try:
                bot_permissions = text_channel.permissions_for(interaction.guild.me)
        
                if bot_permissions.send_messages:
                    # 일반 채팅처럼 표시
                    display_message = (
                        f"🎤 **{interaction.user.display_name}**: {내용}\n"
                        f"└ {language_emoji} {voice_info['name']}"
                    )
                    
                    await text_channel.send(display_message)
                    logger.info(f"📝 채널에 TTS 메시지 표시: {text_channel.name}")
                else:
                    logger.warning(f"⚠️ 채널에 메시지 전송 권한 없음: {text_channel.name}")

            except discord.Forbidden:
                logger.error(f"⚠️ 채널에 메시지 전송 권한 없음: {interaction.channel.name}")
            except Exception as e:
                logger.error(f"⚠️ 채널 메시지 표시 오류: {e}")
        
        logger.info(f"🎤 TTS 큐 추가: {interaction.user.display_name} > '{내용[:30]}...' (대기: {queue_size})")

    @app_commands.command(name="볼륨설정", description="TTS 음성의 속도와 피치를 조절합니다")
    @app_commands.describe(
        속도="재생 속도 (-50 ~ +100, 0이 기본값)",
        피치="음성 높이 (-200 ~ +200, 0이 기본값)"
    )
    async def volume_settings(self, interaction: discord.Interaction, 속도: int, 피치: int = 0):
        """TTS 볼륨 설정 조절"""
        guild_id = str(interaction.guild.id)
        
        # 입력 검증
        if not -50 <= 속도 <= 100:
            embed = discord.Embed(
                title="⌛ 잘못된 속도 값",
                description="속도는 **-50**에서 **+100** 사이로 설정해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if not -200 <= 피치 <= 200:
            embed = discord.Embed(
                title="⌛ 잘못된 피치 값", 
                description="피치는 **-200**에서 **+200** 사이로 설정해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 설정 업데이트
        if guild_id not in self.tts_settings:
            self.tts_settings[guild_id] = {
                'voice': '인준',
                'rate': f'+{속도}%' if 속도 >= 0 else f'{속도}%',
                'pitch': f'+{피치}Hz' if 피치 >= 0 else f'{피치}Hz',
                'volume': '+0%',
                'last_used': time.time()
            }
        else:
            self.tts_settings[guild_id]['rate'] = f'+{속도}%' if 속도 >= 0 else f'{속도}%'
            self.tts_settings[guild_id]['pitch'] = f'+{피치}Hz' if 피치 >= 0 else f'{피치}Hz'
            self.tts_settings[guild_id]['last_used'] = time.time()
        
        # 설정 설명
        speed_desc = "빠르게" if 속도 > 20 else "느리게" if 속도 < -20 else "보통"
        pitch_desc = "높게" if 피치 > 50 else "낮게" if 피치 < -50 else "보통"
        
        embed = discord.Embed(
            title="⚙️ 볼륨 설정 완료",
            description="음성 설정이 업데이트되었습니다!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="🎚️ 설정된 값",
            value=f"속도: **{속도:+d}%** ({speed_desc})\n"
                  f"피치: **{피치:+d}Hz** ({pitch_desc})",
            inline=False
        )
        
        embed.add_field(
            name="🧪 테스트",
            value="`/말하기 설정이 변경되었습니다. 어떻게 들리나요?`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"⚙️ 볼륨 설정: {interaction.guild.name} -> 속도: {속도}%, 피치: {피치}Hz")

    @app_commands.command(name="현재볼륨", description="현재 TTS 설정을 확인합니다")
    async def current_volume(self, interaction: discord.Interaction):
        """현재 TTS 설정 확인 (쓰레드 정보 포함)"""
        guild_id = str(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔊 현재 TTS 설정",
            color=0x0099ff
        )
        
        # 서버의 활성 채널 확인
        connected_channels = self._get_guild_connected_channels(guild_id)
        
        if connected_channels:
            channel_info = []
            for ch_info in connected_channels:
                channel = ch_info['channel']
                queue_size = ch_info['queue_size']
                ch_id = ch_info['channel_id']
                vc = self.voice_clients[ch_id]
                
                status = "🔊 재생중" if vc.is_playing() else "⏸️ 대기중"
                queue_status = f"(대기: {queue_size}개)" if queue_size > 0 else ""
                thread_status = "📝" if ch_id in self.tts_threads else "❌"
                
                channel_info.append(
                    f"• **{channel.name}** {status} {queue_status}\n"
                    f"  └ 기록: {thread_status}"
                )
            
            embed.add_field(
                name=f"🤖 봇 상태 ({len(connected_channels)}개 채널)",
                value="\n".join(channel_info),
                inline=False
            )
        else:
            embed.add_field(
                name="🤖 봇 상태",
                value="연결: ❌ 미연결\n먼저 `/입장`을 해주세요",
                inline=False
            )
        
        # TTS 설정 (서버 전역)
        if guild_id in self.tts_settings:
            settings = self.tts_settings[guild_id]
            current_voice = settings['voice']
            voice_info = self.korean_voices[current_voice]
            
            if voice_info:
                # 언어 이모지
                lang_emoji = "🇰🇷" if voice_info['language'] == 'ko' else "🇺🇸" if 'US' in voice_info['language'] else "🇬🇧" if 'GB' in voice_info['language'] else "🇦🇺"
                
                embed.add_field(
                    name="🎭 음성 설정 (서버 공통)",
                    value=f"{lang_emoji} {voice_info['name']}\n"
                        f"성별: {voice_info['gender']}\n"
                        f"스타일: {voice_info['style']}\n"
                        f"언어: {voice_info['language']}",
                    inline=True
                )
            
            embed.add_field(
                name="🎚️ 볼륨 설정",
                value=f"속도: {settings['rate']}\n"
                    f"피치: {settings['pitch']}\n"
                    f"마지막 사용: {time.time() - settings['last_used']:.0f}초 전",
                inline=True
            )
        else:
            embed.add_field(
                name="🎭 음성 설정",
                value="기본값으로 설정됩니다",
                inline=True
            )
        
        embed.add_field(
            name="🎵 목소리 정보",
            value=f"총 **14가지** 목소리 사용 가능\n"
                f"🇰🇷 한국어: 9가지\n"
                f"🇺🇸🇬🇧🇦🇺 영어: 5가지",
            inline=False
        )
        
        embed.add_field(
            name="📖 사용법",
            value="`/말하기 안녕하세요 지민` - 지민 목소리로 재생\n"
                "`/볼륨설정 +20 -10` - 속도 빠르게, 피치 낮게\n",
            inline=False
        )
        
        embed.set_footer(text="💡 모든 대화는 쓰레드에 자동 기록됩니다!")
        
        await interaction.response.send_message(embed=embed)

    # @app_commands.command(name="대기열", description="현재 음성 채널의 TTS 대기열을 확인합니다")
    # async def tts_queue(self, interaction: discord.Interaction):
    #     """현재 채널의 TTS 대기열 확인"""
        
    #     # 사용자가 음성 채널에 있는지 확인
    #     if not interaction.user.voice:
    #         embed = discord.Embed(
    #             title="⏸️ 음성 채널 필요",
    #             description="음성 채널에 입장한 후 명령어를 사용해주세요!",
    #             color=0xff0000
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return
        
    #     user_channel = interaction.user.voice.channel
    #     channel_id = str(user_channel.id)
        
    #     if channel_id not in self.tts_queues:
    #         embed = discord.Embed(
    #             title="ℹ️ 큐 없음",
    #             description=f"**{user_channel.name}**에서 먼저 `/입장` 명령어를 사용해주세요!",
    #             color=0x0099ff
    #         )
    #         await interaction.response.send_message(embed=embed, ephemeral=True)
    #         return
        
    #     queue = self.tts_queues[channel_id]
    #     queue_size = queue.qsize()
        
    #     embed = discord.Embed(
    #         title=f"📋 TTS 대기열 - {user_channel.name}",
    #         color=0x0099ff
    #     )
        
    #     if queue_size == 0:
    #         embed.description = "현재 대기 중인 TTS가 없습니다."
    #     else:
    #         embed.description = f"**{queue_size}개**의 TTS가 대기 중입니다."
            
    #         # 큐 내용 미리보기 (처음 5개만)
    #         queue_items = []
    #         temp_queue = list(queue._queue)[:5]
            
    #         for idx, item in enumerate(temp_queue, 1):
    #             user_name = item['user'].display_name
    #             text_preview = item['text'][:30] + ('...' if len(item['text']) > 30 else '')
    #             voice_name = self.korean_voices[item['voice']]['name']
    #             queue_items.append(
    #                 f"**{idx}.** {user_name}: {text_preview}\n"
    #                 f"└ 목소리: {voice_name}"
    #             )
            
    #         if queue_items:
    #             embed.add_field(
    #                 name="🎵 대기 중인 항목",
    #                 value="\n\n".join(queue_items),
    #                 inline=False
    #             )
            
    #         if queue_size > 5:
    #             embed.set_footer(text=f"...외 {queue_size - 5}개 더")
        
    #     # 현재 재생 상태
    #     if channel_id in self.voice_clients:
    #         voice_client = self.voice_clients[channel_id]
    #         if voice_client.is_playing():
    #             embed.add_field(
    #                 name="🔊 재생 상태",
    #                 value="현재 TTS를 재생 중입니다.",
    #                 inline=False
    #             )
        
    #     # 쓰레드 링크 추가
    #     if channel_id in self.tts_threads:
    #         thread = self.tts_threads[channel_id]
    #         embed.add_field(
    #             name="📝 대화 기록",
    #             value=f"[쓰레드에서 전체 기록 보기]({thread.jump_url})",
    #             inline=False
    #         )
        
    #     await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="퇴장", description="TTS 봇을 현재 음성 채널에서 퇴장시킵니다")
    async def tts_leave(self, interaction: discord.Interaction):
        """TTS 봇 음성 채널 퇴장 (사용자가 있는 채널에서)"""
        
        # 사용자가 음성 채널에 있는지 확인
        if not interaction.user.voice:
            embed = discord.Embed(
                title="⏸️ 음성 채널 필요",
                description="음성 채널에 입장한 후 명령어를 사용해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_channel = interaction.user.voice.channel
        channel_id = str(user_channel.id)
        
        if channel_id not in self.voice_clients:
            embed = discord.Embed(
                title="ℹ️ 연결되지 않음",
                description=f"**{user_channel.name}**에 봇이 연결되어 있지 않습니다.",
                color=0x0099ff
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            voice_client = self.voice_clients[channel_id]
            channel_name = voice_client.channel.name
            guild_id = str(voice_client.guild.id)
            
            # 채널 정리
            await self._cleanup_channel(channel_id)
            
            # 남은 활성 채널 수 확인
            remaining_channels = self._get_guild_connected_channels(guild_id)
            
            # 성공 메시지
            embed = discord.Embed(
                title="👋 TTS 봇 퇴장",
                description=f"**{channel_name}**에서 퇴장했습니다.",
                color=0x00ff00
            )
            
            if remaining_channels:
                embed.add_field(
                    name="🔀 다른 활성 채널",
                    value=f"{len(remaining_channels)}개의 채널에서 여전히 활성화되어 있습니다.",
                    inline=False
                )
            
            embed.set_footer(text="다시 사용하려면 /입장 명령어를 사용해주세요!")
            
            await interaction.response.send_message(embed=embed)
            logger.info(
                f"👋 TTS 봇 퇴장: {interaction.guild.name} > {channel_name} "
                f"(남은 채널: {len(remaining_channels)})"
            )
            
        except Exception as e:
            embed = discord.Embed(
                title="⏸️ 퇴장 실패",
                description=f"퇴장 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            logger.error(f"⏸️ TTS 퇴장 오류: {e}", exc_info=True)

    @tts_setup.command(name="전용채널", description="자동 TTS가 적용될 전용 채널을 설정합니다")
    @app_commands.describe(채널="TTS 전용 채널 (없음 선택 시 해제)")
    @app_commands.default_permissions(manage_guild=True)
    async def set_dedicated_channel(
        self, 
        interaction: discord.Interaction, 
        채널: Optional[discord.TextChannel] = None
    ):
        """TTS 전용 채널 설정"""
        guild_id = str(interaction.guild.id)
        
        if 채널 is None:
            # 전용 채널 해제
            success = await self.bot.db_manager.set_tts_dedicated_channel(guild_id, None)
            
            if success:
                embed = discord.Embed(
                    title="✅ TTS 전용 채널 해제",
                    description="자동 TTS 기능이 비활성화되었습니다.",
                    color=0x00ff00
                )
            else:
                embed = discord.Embed(
                    title="❌ 설정 실패",
                    description="전용 채널 해제 중 오류가 발생했습니다.",
                    color=0xff0000
                )
            
            await interaction.response.send_message(embed=embed)
            return
        
        # 권한 확인
        bot_permissions = 채널.permissions_for(interaction.guild.me)
        if not all([bot_permissions.read_messages, bot_permissions.send_messages]):
            embed = discord.Embed(
                title="⛔ 권한 부족",
                description=f"{채널.mention}에 메시지 읽기/보내기 권한이 필요합니다.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 설정 저장
        channel_id = str(채널.id)
        success = await self.bot.db_manager.set_tts_dedicated_channel(guild_id, channel_id)
        
        if success:
            embed = discord.Embed(
                title="✅ TTS 전용 채널 설정 완료",
                description=f"{채널.mention}에서 자동 TTS가 활성화됩니다.",
                color=0x00ff00
            )
            embed.add_field(
                name="📌 사용 방법",
                value="• 봇이 음성 채널에 `/입장` 상태일 때\n"
                    "• 해당 채널에 일반 메시지 입력\n"
                    "• 명령어 없이 자동으로 TTS 재생됩니다",
                inline=False
            )
            embed.add_field(
                name="⚙️ 필터링",
                value="• 2글자 미만 메시지 무시\n"
                    "• 이모지만 있는 메시지 무시\n"
                    "• 봇 메시지 무시",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ 설정 실패",
                description="전용 채널 설정 중 오류가 발생했습니다.",
                color=0xff0000
            )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"✅ TTS 전용 채널 설정: {interaction.guild.name} -> #{채널.name}")


    @app_commands.command(name="내목소리", description="나의 기본 TTS 목소리를 설정합니다")
    @app_commands.describe(
        목소리="사용할 기본 목소리"
    )
    async def set_my_voice(
        self, 
        interaction: discord.Interaction,
        목소리: Literal[
            '인준', '선희', '현수', '국민', '봉진', '지민', '서현', '순복', '유진',
            'Guy', 'Jenny', 'Aria', 'William',
            'Alvaro', 'Elvira', 'Jorge', 'Dalia',
            'Yunxi', 'Xiaoxiao', 'Yunyang', 'Xiaoyi', 
            'YunJhe', 'HsiaoChen', 'WanLung', 'HiuMaan'
        ]
    ):
        """개인 기본 목소리 설정"""
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # 목소리 정보 확인
        voice_info = self.all_voices.get(목소리)
        if not voice_info:
            await interaction.response.send_message(
                "❌ 올바르지 않은 목소리입니다!",
                ephemeral=True
            )
            return
        
        # DB에 저장
        success = await self.bot.db_manager.set_user_tts_preference(
            guild_id, user_id, 목소리
        )
        
        if success:
            lang = voice_info.get('language', 'ko-KR')
            language_emoji = (
                "🇰🇷" if 'ko' in lang.lower()
                else "🇪🇸" if 'es' in lang.lower()
                else "🇨🇳" if 'zh' in lang.lower()
                else "🇺🇸" if 'US' in lang 
                else "🇬🇧" if 'GB' in lang 
                else "🇦🇺" if 'AU' in lang
                else "🌐"
            )
            
            embed = discord.Embed(
                title="✅ 기본 목소리 설정 완료",
                description=f"앞으로 **{interaction.guild.name}**에서는\n"
                        f"자동으로 이 목소리가 사용됩니다!",
                color=0x00ff00
            )
            embed.add_field(
                name="🎭 선택한 목소리",
                value=f"{language_emoji} **{voice_info['name']}**\n"
                    f"성별: {voice_info['gender']}\n"
                    f"스타일: {voice_info['style']}",
                inline=False
            )
            embed.add_field(
                name="💡 적용 범위",
                value="• TTS 전용 채널에서 자동 TTS\n"
                    "• `/말하기` 명령어 사용 시 (목소리 미지정 시)",
                inline=False
            )
            embed.set_footer(text="테스트: /말하기 안녕하세요")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"🎤 개인 목소리 설정: {interaction.user.display_name} -> {목소리}")
        else:
            await interaction.response.send_message(
                "❌ 설정 저장 중 오류가 발생했습니다.",
                ephemeral=True
            )


    @app_commands.command(name="내목소리확인", description="현재 설정된 나의 기본 목소리를 확인합니다")
    async def check_my_voice(self, interaction: discord.Interaction):
        """개인 목소리 설정 확인"""
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        # DB에서 조회
        preference = await self.bot.db_manager.get_user_tts_preference(guild_id, user_id)
        
        embed = discord.Embed(
            title="🎤 나의 TTS 설정",
            color=0x0099ff
        )
        
        if preference:
            voice_name = preference['voice']
            voice_info = self.all_voices.get(voice_name, {})
            
            lang = voice_info.get('language', 'ko-KR')
            language_emoji = (
                "🇰🇷" if 'ko' in lang.lower()
                else "🇪🇸" if 'es' in lang.lower()
                else "🇨🇳" if 'zh' in lang.lower()
                else "🇺🇸" if 'US' in lang 
                else "🇬🇧" if 'GB' in lang 
                else "🇦🇺" if 'AU' in lang
                else "🌐"
            )
            
            embed.add_field(
                name="🎭 현재 목소리",
                value=f"{language_emoji} **{voice_info.get('name', voice_name)}**\n"
                    f"성별: {voice_info.get('gender', '?')}\n"
                    f"스타일: {voice_info.get('style', '?')}",
                inline=False
            )
            embed.add_field(
                name="⚙️ 세부 설정",
                value=f"속도: {preference['rate']}\n"
                    f"피치: {preference['pitch']}\n"
                    f"볼륨: {preference['volume']}",
                inline=False
            )
        else:
            embed.description = "아직 설정된 목소리가 없습니다.\n`/내목소리` 명령어로 설정해보세요!"
            embed.add_field(
                name="🎯 기본 목소리",
                value="서버 기본 설정(인준)이 사용됩니다.",
                inline=False
            )
        
        embed.add_field(
            name="💡 변경 방법",
            value="`/내목소리 [목소리명]`",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tts상태확인", description="현재 TTS 자동 재생 상태를 확인합니다")
    async def check_tts_status(self, interaction: discord.Interaction):
        """[디버그] 현재 TTS 상태 종합 확인"""
        
        user = interaction.user
        guild = interaction.guild
        guild_id = str(guild.id)
        
        embed = discord.Embed(
            title="🔍 TTS 자동 재생 상태 진단",
            description="현재 TTS 자동 재생이 가능한 상태인지 확인합니다.",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 1. 음성 채널 입장 상태 확인
        voice_status = "❌"
        voice_detail = "음성 채널에 입장하지 않음"
        user_channel_id = None
        
        if user.voice and user.voice.channel:
            voice_status = "✅"
            voice_detail = f"{user.voice.channel.name}에 입장 중"
            user_channel_id = str(user.voice.channel.id)
        
        embed.add_field(
            name=f"{voice_status} 1단계: 음성 채널 입장",
            value=voice_detail,
            inline=False
        )
        
        # 2. TTS 전용 채널 설정 확인
        settings = await self.bot.db_manager.get_tts_channel_settings(guild_id)
        
        tts_channel_status = "❌"
        tts_channel_detail = "TTS 전용 채널이 설정되지 않음"
        tts_channel_id = None
        tts_channel = None
        
        if settings and settings.get('channel_id'):
            tts_channel_id = settings['channel_id']
            tts_channel = guild.get_channel(int(tts_channel_id))
            if tts_channel:
                tts_channel_status = "✅"
                tts_channel_detail = f"#{tts_channel.name} (ID: {tts_channel_id})"
        
        embed.add_field(
            name=f"{tts_channel_status} 2단계: TTS 전용 채널 설정",
            value=tts_channel_detail,
            inline=False
        )
        
        # 3. 현재 채널이 TTS 전용 채널인지 확인
        current_channel_status = "❌"
        current_channel_detail = "TTS 전용 채널이 아님"
        current_channel_id = str(interaction.channel.id)
        
        if tts_channel_id == current_channel_id:
            current_channel_status = "✅"
            current_channel_detail = f"현재 채널이 TTS 전용 채널입니다"
        else:
            current_channel_detail = f"현재: #{interaction.channel.name}\nTTS 채널로 이동하세요: {f'#{tts_channel.name}' if tts_channel else '없음'}"
        
        embed.add_field(
            name=f"{current_channel_status} 3단계: TTS 전용 채널 위치",
            value=current_channel_detail,
            inline=False
        )
        
        # 4. 봇 연결 상태 확인
        bot_status = "❌"
        bot_detail = "봇이 음성 채널에 연결되지 않음"
        
        if user_channel_id:
            if user_channel_id in self.voice_clients:
                voice_client = self.voice_clients[user_channel_id]
                if voice_client.is_connected():
                    bot_status = "✅"
                    bot_detail = f"봇이 같은 채널({user.voice.channel.name})에 연결됨"
                else:
                    bot_detail = "봇 연결이 끊어짐 (재입장 필요)"
            else:
                # 다른 채널에 봇이 있는지 확인
                if self.voice_clients:
                    other_channels = []
                    for ch_id, vc in self.voice_clients.items():
                        if vc.is_connected():
                            other_channels.append(vc.channel.name)
                    if other_channels:
                        bot_detail = f"봇이 다른 채널에 연결됨: {', '.join(other_channels)}\n→ 사용자가 있는 채널에서 `/입장` 실행 필요"
                else:
                    bot_detail = "봇이 어떤 음성 채널에도 연결되지 않음\n→ `/입장` 명령어로 봇을 입장시키세요"
        
        embed.add_field(
            name=f"{bot_status} 4단계: 봇 연결 상태",
            value=bot_detail,
            inline=False
        )
        
        # 5. TTS 큐 상태
        queue_status = "❌"
        queue_detail = "큐 없음"
        
        if user_channel_id and user_channel_id in self.tts_queues:
            queue = self.tts_queues[user_channel_id]
            queue_size = queue.qsize()
            queue_status = "✅"
            queue_detail = f"대기 중인 TTS: {queue_size}개"
            
            if user_channel_id in self.voice_clients:
                voice_client = self.voice_clients[user_channel_id]
                if voice_client.is_playing():
                    queue_detail += "\n🔊 현재 재생 중"
        
        embed.add_field(
            name=f"{queue_status} 5단계: TTS 큐 상태",
            value=queue_detail,
            inline=False
        )
        
        # 종합 진단
        all_ok = (
            voice_status == "✅" and
            tts_channel_status == "✅" and
            current_channel_status == "✅" and
            bot_status == "✅"
        )
        
        if all_ok:
            embed.add_field(
                name="🎉 종합 진단 결과",
                value="✅ **모든 조건이 충족되었습니다!**\n"
                      "이제 메시지를 입력하면 자동으로 TTS가 재생됩니다.\n\n"
                      "테스트: `안녕하세요` 라고 입력해보세요!",
                inline=False
            )
            embed.color = 0x00ff00
        else:
            problems = []
            if voice_status == "❌":
                problems.append("❌ 음성 채널에 입장하세요")
            if tts_channel_status == "❌":
                problems.append("❌ `/tts설정전용채널` 명령어로 TTS 채널을 설정하세요")
            if current_channel_status == "❌":
                problems.append(f"❌ TTS 전용 채널({tts_channel.mention if tts_channel else '없음'})로 이동하세요")
            if bot_status == "❌":
                problems.append("❌ 음성 채널에서 `/입장` 명령어를 실행하세요")
            
            embed.add_field(
                name="⚠️ 종합 진단 결과",
                value="**자동 TTS가 작동하지 않습니다.**\n\n" + "\n".join(problems),
                inline=False
            )
            embed.color = 0xff0000
        
        # 추가 정보
        embed.set_footer(text=f"요청자: {user.display_name}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tts로그확인", description="[관리자] TTS 자동 재생 로그를 확인합니다")
    @app_commands.default_permissions(administrator=True)
    async def check_tts_logs(self, interaction: discord.Interaction):
        """[관리자] TTS 로그 확인"""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.",
                ephemeral=True
            )
            return
        
        guild_id = str(interaction.guild.id)
        
        embed = discord.Embed(
            title="📋 TTS 시스템 로그",
            color=0x0099ff,
            timestamp=datetime.now()
        )
        
        # 1. 연결된 채널 목록
        if self.voice_clients:
            channels = []
            for ch_id, vc in self.voice_clients.items():
                if vc.is_connected() and str(vc.guild.id) == guild_id:
                    queue_size = self.tts_queues[ch_id].qsize() if ch_id in self.tts_queues else 0
                    is_playing = "🔊 재생 중" if vc.is_playing() else "⏸️ 대기"
                    channels.append(f"• {vc.channel.name} - {is_playing} (큐: {queue_size})")
            
            if channels:
                embed.add_field(
                    name="🎤 현재 연결된 음성 채널",
                    value="\n".join(channels),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🎤 현재 연결된 음성 채널",
                    value="없음",
                    inline=False
                )
        else:
            embed.add_field(
                name="🎤 현재 연결된 음성 채널",
                value="없음",
                inline=False
            )
        
        # 2. TTS 전용 채널 설정
        settings = await self.bot.db_manager.get_tts_channel_settings(guild_id)
        if settings and settings.get('channel_id'):
            channel = interaction.guild.get_channel(int(settings['channel_id']))
            if channel:
                filters = []
                if settings.get('filter_bot', True):
                    filters.append("✅ 봇 메시지 필터링")
                if settings.get('filter_short', True):
                    min_len = settings.get('min_length', 2)
                    filters.append(f"✅ {min_len}글자 미만 필터링")
                if settings.get('filter_emoji', True):
                    filters.append("✅ 이모지 전용 메시지 필터링")
                
                embed.add_field(
                    name="📝 TTS 전용 채널 설정",
                    value=f"채널: {channel.mention}\n" + "\n".join(filters),
                    inline=False
                )
        else:
            embed.add_field(
                name="📝 TTS 전용 채널 설정",
                value="❌ 설정되지 않음",
                inline=False
            )
        
        # 3. 세션 정보
        if self.session_message_counts:
            session_info = []
            for ch_id, count in self.session_message_counts.items():
                if ch_id in self.voice_clients:
                    vc = self.voice_clients[ch_id]
                    if str(vc.guild.id) == guild_id:
                        session_info.append(f"• {vc.channel.name}: {count}개 메시지")
            
            if session_info:
                embed.add_field(
                    name="📊 현재 세션 통계",
                    value="\n".join(session_info),
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _get_guild_connected_channels(self, guild_id: str) -> list:
        """특정 서버에서 봇이 연결된 채널 목록 반환"""
        connected = []
        for channel_id, voice_client in self.voice_clients.items():
            if voice_client.is_connected() and str(voice_client.guild.id) == guild_id:
                connected.append({
                    'channel_id': channel_id,
                    'channel': voice_client.channel,
                    'queue_size': self.tts_queues.get(channel_id, asyncio.Queue()).qsize()
                })
        return connected

    async def _process_tts_queue(self, channel_id: str):
        """TTS 큐를 순차적으로 처리하는 백그라운드 태스크"""
        
        channel_info = "Unknown"
        if channel_id in self.voice_clients:
            vc = self.voice_clients[channel_id]
            if vc.channel:
                channel_info = f"{vc.channel.guild.name} > {vc.channel.name}"
        
        logger.info(f"🎬 큐 프로세서 시작: {channel_info} (ID: {channel_id})")
        
        try:
            while True:
                tts_request = await self.tts_queues[channel_id].get()
                
                try:
                    user = tts_request['user']
                    user_id = tts_request.get('user_id')
                    text = tts_request['text']
                    voice = tts_request['voice']
                    channel_name = tts_request.get('channel_name', 'Unknown')
                    request_time = tts_request.get('timestamp', time.time())
                    auto_tts = tts_request.get('auto_tts', False)
                    
                    voice_info = self.all_voices[voice]
                    logger.info(
                        f"🎵 TTS 처리 시작: {user.display_name} > "
                        f"'{text[:30]}...' @ {channel_name} {'(자동)' if auto_tts else ''}"
                    )
                    
                    if channel_id not in self.voice_clients:
                        logger.warning(f"⚠️ VoiceClient 없음, 큐 처리 중단: {channel_id}")
                        break
                    
                    voice_client = self.voice_clients[channel_id]
                    if not voice_client.is_connected():
                        logger.warning(f"⚠️ 음성 연결 끊김, 큐 처리 중단: {channel_id}")
                        break
                    
                    guild_id = str(voice_client.guild.id)
                    
                    # TTS 파일 생성 (user_id 전달)
                    audio_file = await self._create_edge_tts_file(text, guild_id, voice, user_id)
                    
                    if not audio_file:
                        logger.error(f"❌ TTS 파일 생성 실패: {text[:30]}")
                        
                        # 실패도 로그에 기록
                        await self._log_to_thread(
                            channel_id=channel_id,
                            guild_id=guild_id,
                            voice_channel_name=channel_name,
                            user=user,
                            text=text,
                            voice=voice,
                            request_time=request_time,
                            success=False,
                            auto_tts=auto_tts
                        )
                        continue
                    
                    # 오디오 재생
                    success = await self._play_audio_and_wait(voice_client, audio_file, text)
                    
                    # 쓰레드에 기록
                    await self._log_to_thread(
                        channel_id=channel_id,
                        guild_id=guild_id,
                        voice_channel_name=channel_name,
                        user=user,
                        text=text,
                        voice=voice,
                        request_time=request_time,
                        success=success,
                        auto_tts=auto_tts
                    )
                    
                    if success:
                        logger.info(f"✅ TTS 재생 완료: {user.display_name} @ {channel_name}")
                    else:
                        logger.error(f"❌ TTS 재생 실패: {user.display_name} @ {channel_name}")
                    
                    self.tts_queues[channel_id].task_done()
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ TTS 처리 중 오류: {e}", exc_info=True)
                    self.tts_queues[channel_id].task_done()
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"🛑 큐 프로세서 중지: {channel_info}")
            raise
        except Exception as e:
            logger.error(f"❌ 큐 프로세서 오류: {e}", exc_info=True)

    async def _get_or_create_daily_log_thread(self, guild_id: str) -> Optional[discord.Thread]:
        try:
            # 오늘 날짜 (한국 시간 기준)
            from datetime import datetime, timezone, timedelta
            kst = timezone(timedelta(hours=9))
            today = datetime.now(kst).strftime('%Y-%m-%d')
            today_display = datetime.now(kst).strftime('%Y년 %m월 %d일')
            
            cache_key = f"{guild_id}_{today}"
            
            if cache_key in self.daily_threads_cache:
                thread = self.daily_threads_cache[cache_key]
                logger.debug(f"📦 캐시에서 일별 쓰레드 발견: {thread.name}")
                return thread
            
            async with self.bot.db_manager.get_connection() as db:
                cursor = await db.execute(
                    'SELECT thread_id FROM tts_daily_threads WHERE guild_id = ? AND date = ?',
                    (guild_id, today)
                )
                result = await cursor.fetchone()
            
            if result:
                thread_id = int(result[0])
                logger.debug(f"💾 DB에서 일별 쓰레드 ID 발견: {thread_id}")
                
                try:
                    # Discord에서 쓰레드 객체 가져오기
                    thread = await self.bot.fetch_channel(thread_id)
                    
                    if isinstance(thread, discord.Thread):
                        # 쓰레드가 유효함 - 캐시에 저장
                        self.daily_threads_cache[cache_key] = thread
                        logger.info(f"✅ DB에서 일별 쓰레드 복원: {thread.name}")
                        return thread
                    else:
                        logger.warning(f"⚠️ ID {thread_id}는 쓰레드가 아님")
                        
                except discord.NotFound:
                    logger.warning(f"⚠️ DB의 쓰레드 ID {thread_id}를 찾을 수 없음 (삭제됨)")
                    # DB에서 삭제
                    async with self.bot.db_manager.get_connection() as db:
                        await db.execute(
                            'DELETE FROM tts_daily_threads WHERE guild_id = ? AND date = ?',
                            (guild_id, today)
                        )
                        await db.commit()
                except discord.HTTPException as e:
                    logger.error(f"⚠️ 쓰레드 fetch 오류: {e}")
            
            async with self.bot.db_manager.get_connection() as db:
                cursor = await db.execute(
                    'SELECT log_channel_id, enabled FROM tts_log_settings WHERE guild_id = ?',
                    (guild_id,)
                )
                settings_result = await cursor.fetchone()
            
            if not settings_result or not settings_result[0] or not settings_result[1]:
                logger.info(f"📝 로그 채널 미설정 또는 비활성화: {guild_id}")
                return None
            
            log_channel_id = int(settings_result[0])
            log_channel = self.bot.get_channel(log_channel_id)
            
            if not log_channel:
                logger.warning(f"⚠️ 로그 채널을 찾을 수 없음: {log_channel_id}")
                return None
            
            if not isinstance(log_channel, discord.TextChannel):
                logger.error(f"⚠️ 로그 채널이 텍스트 채널이 아님: {log_channel_id}")
                return None

            bot_permissions = log_channel.permissions_for(log_channel.guild.me)
            
            if not all([
                bot_permissions.send_messages,
                bot_permissions.create_public_threads,
                bot_permissions.send_messages_in_threads
            ]):
                logger.error(
                    f"⚠️ 로그 채널에 필요한 권한 부족: {log_channel.name}\n"
                    f"   메시지 보내기: {bot_permissions.send_messages}\n"
                    f"   쓰레드 생성: {bot_permissions.create_public_threads}\n"
                    f"   쓰레드에 메시지: {bot_permissions.send_messages_in_threads}"
                )
                return None
            
            thread_name = f"[{datetime.now(kst).strftime('%m/%d')}] TTS 대화 기록"
            
            # 초기 임베드 생성
            initial_embed = discord.Embed(
                title=f"📊 {today_display} TTS 활동",
                description=(
                    f"오늘의 모든 TTS 대화가 이곳에 기록됩니다."
                    # f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    # f"📈 **실시간 통계**\n"
                    # f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    # f"🎤 활성 세션: 0개\n"
                    # f"💬 총 메시지: 0개\n"
                    # f"👥 참여자: 0명\n"
                    # f"━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=0x00ff00,
                timestamp=datetime.now(kst)
            )
            
            initial_embed.set_footer(
                text="💡 이 쓰레드는 자정에 자동으로 보관됩니다",
                icon_url=self.bot.user.display_avatar.url if self.bot.user else None
            )
            
            # 로그 채널에 메시지 전송
            try:
                initial_message = await log_channel.send(embed=initial_embed)
                logger.info(f"📤 일별 로그 초기 메시지 전송: {log_channel.name}")
            except discord.Forbidden:
                logger.error(f"⚠️ 로그 채널에 메시지 전송 권한 없음: {log_channel.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"⚠️ 로그 채널에 메시지 전송 실패: {e}")
                return None
            
            # 쓰레드 생성
            try:
                thread = await initial_message.create_thread(
                    name=thread_name,
                    auto_archive_duration=1440  # 24시간
                )
                logger.info(f"🧵 일별 TTS 로그 쓰레드 생성: {thread_name} (ID: {thread.id})")
            except discord.Forbidden:
                logger.error(f"⚠️ 쓰레드 생성 권한 없음: {log_channel.name}")
                return None
            except discord.HTTPException as e:
                logger.error(f"⚠️ 쓰레드 생성 실패: {e}")
                return None

            try:
                async with self.bot.db_manager.get_connection() as db:
                    await db.execute(
                        '''
                        INSERT INTO tts_daily_threads (guild_id, date, thread_id, message_count, created_at)
                        VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                        ''',
                        (guild_id, today, str(thread.id))
                    )
                    await db.commit()
                logger.info(f"💾 일별 쓰레드 DB 저장 완료: {guild_id} - {today}")
            except Exception as e:
                logger.error(f"⚠️ 일별 쓰레드 DB 저장 실패: {e}", exc_info=True)
                # DB 저장 실패해도 쓰레드는 사용 가능
            
            self.daily_threads_cache[cache_key] = thread
            logger.info(f"✅ 일별 로그 쓰레드 준비 완료: {thread.name}")
            
            return thread
            
        except Exception as e:
            logger.error(f"⚠️ 일별 로그 쓰레드 생성 중 예상치 못한 오류: {e}", exc_info=True)
            return None

    async def _increment_message_count(self, guild_id: str):
        """DB의 메시지 카운트 증가"""
        try:
            from datetime import datetime, timezone, timedelta
            kst = timezone(timedelta(hours=9))
            today = datetime.now(kst).strftime('%Y-%m-%d')
            
            async with self.bot.db_manager.get_connection() as db:
                await db.execute(
                    '''
                    UPDATE tts_daily_threads 
                    SET message_count = message_count + 1 
                    WHERE guild_id = ? AND date = ?
                    ''',
                    (guild_id, today)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"⚠️ 메시지 카운트 증가 실패: {e}")

    async def _log_session_start(self, guild_id: str, voice_channel_name: str, starter: discord.Member):
        """
        세션 시작 구분선 로그
        
        Args:
            guild_id: Discord 서버 ID
            voice_channel_name: 음성 채널 이름
            starter: 세션을 시작한 사용자
        """
        try:
            thread = await self._get_or_create_daily_log_thread(guild_id)
            if not thread:
                return
            
            separator = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎤 **[{voice_channel_name}]** 세션 시작\n"
                f"⏰ <t:{int(time.time())}:T> | 👤 {starter.display_name}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            
            await thread.send(separator)
            logger.info(f"📝 세션 시작 로그: {voice_channel_name}")
            
        except discord.Forbidden:
            logger.error(f"⚠️ 세션 시작 로그 권한 없음: {guild_id}")
        except Exception as e:
            logger.error(f"⚠️ 세션 시작 로그 오류: {e}", exc_info=True)
    
    async def _log_session_end(self, guild_id: str, voice_channel_name: str, channel_id: str):
        """
        세션 종료 구분선 로그
        
        Args:
            guild_id: Discord 서버 ID
            voice_channel_name: 음성 채널 이름
            channel_id: 음성 채널 ID (메시지 카운트 조회용)
        """
        try:
            thread = await self._get_or_create_daily_log_thread(guild_id)
            if not thread:
                return
            
            # 이 세션의 메시지 수
            message_count = self.session_message_counts.get(channel_id, 0)
            
            separator = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔚 **[{voice_channel_name}]** 세션 종료\n"
                f"⏰ <t:{int(time.time())}:T> | 📊 메시지: {message_count}개\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
            )
            
            await thread.send(separator)
            logger.info(f"📝 세션 종료 로그: {voice_channel_name} ({message_count}개 메시지)")
            
            # 카운트 초기화
            if channel_id in self.session_message_counts:
                del self.session_message_counts[channel_id]
            
        except discord.Forbidden:
            logger.error(f"⚠️ 세션 종료 로그 권한 없음: {guild_id}")
        except Exception as e:
            logger.error(f"⚠️ 세션 종료 로그 오류: {e}", exc_info=True)

    async def _get_or_create_log_thread(self, channel_id: str, guild_id: str, voice_channel_name: str) -> Optional[discord.Thread]:
        """로그 쓰레드 가져오기 또는 생성 (첫 TTS 시)"""
        
        # 이미 쓰레드가 있으면 반환
        if channel_id in self.tts_threads:
            thread = self.tts_threads[channel_id]
            try:
                await thread.fetch()  # 유효성 확인
                return thread
            except discord.NotFound:
                del self.tts_threads[channel_id]
        
        try:
            # DB에서 로그 채널 설정 조회
            async with self.bot.db_manager.get_connection() as db:
                cursor = await db.execute(
                    'SELECT log_channel_id, enabled FROM tts_log_settings WHERE guild_id = ?',
                    (guild_id,)
                )
                result = await cursor.fetchone()
            
            if not result or not result[0] or not result[1]:
                logger.info(f"📝 로그 채널 미설정: {guild_id}")
                return None
            
            log_channel_id = int(result[0])
            log_channel = self.bot.get_channel(log_channel_id)
            
            if not log_channel:
                logger.warning(f"⚠️ 로그 채널을 찾을 수 없음: {log_channel_id}")
                return None
            
            # 쓰레드 이름 생성
            now = datetime.now()
            thread_name = f"[{now.strftime('%m/%d')}] {voice_channel_name} - {now.strftime('%H:%M')}"
            
            # 쓰레드 생성을 위한 초기 메시지
            initial_embed = discord.Embed(
                title="🎤 TTS 세션 시작",
                description=f"**{voice_channel_name}**의 대화 기록이 시작됩니다.",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            initial_embed.add_field(
                name="📊 세션 정보",
                value=f"🎤 채널: {voice_channel_name}\n"
                      f"⏰ 시작: <t:{int(time.time())}:F>\n"
                      f"📝 기록 형식: 실시간 스트림",
                inline=False
            )
            initial_embed.set_footer(text="이 쓰레드는 24시간 후 자동 보관됩니다")
            
            initial_message = await log_channel.send(embed=initial_embed)
            
            # 쓰레드 생성
            thread = await initial_message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24시간
            )
            
            self.tts_threads[channel_id] = thread
            
            logger.info(f"🧵 TTS 로그 쓰레드 생성: {thread_name} (ID: {thread.id})")
            
            return thread
            
        except discord.Forbidden:
            logger.error(f"⛔ 쓰레드 생성 권한 없음: {guild_id}")
            return None
        except Exception as e:
            logger.error(f"⛔ 쓰레드 생성 오류: {e}", exc_info=True)
            return None

    async def _log_to_thread(
        self, 
        channel_id: str,
        guild_id: str,
        voice_channel_name: str,
        user: discord.Member, 
        text: str, 
        voice: str,
        request_time: float,
        success: bool = True,
        auto_tts: bool = False  # 추가
    ):
        try:
            # 일별 쓰레드 가져오기
            thread = await self._get_or_create_daily_log_thread(guild_id)
            
            if not thread:
                return
            
            voice_info = self.all_voices.get(voice, {})
            lang = voice_info.get('language', 'ko-KR')
            language_emoji = (
                "🇰🇷" if 'ko' in lang.lower()
                else "🇪🇸" if 'es' in lang.lower()
                else "🇨🇳" if 'zh' in lang.lower()
                else "🇺🇸" if 'US' in lang 
                else "🇬🇧" if 'GB' in lang 
                else "🇦🇺" if 'AU' in lang
                else "🌐"
            )
            
            # 자동 TTS 표시
            prefix = "🤖" if auto_tts else "💬"
            channel_prefix = f"**[{voice_channel_name}]**"
            
            if success:
                # 성공 시 일반 메시지
                log_message = (
                    f"{prefix} {channel_prefix} {user.display_name}: {text}\n"
                    f"└ {language_emoji} {voice_info.get('name', voice)} | "
                    f"<t:{int(request_time)}:T>"
                )
            else:
                # 실패 시 오류 표시
                log_message = (
                    f"~~{prefix} {channel_prefix} {user.display_name}: {text}~~\n"
                    f"└ ❌ 재생 실패 | {language_emoji} {voice_info.get('name', voice)} | "
                    f"<t:{int(request_time)}:T>"
                )
            
            await thread.send(log_message)
            
            # 세션별 메시지 카운트 증가
            if channel_id not in self.session_message_counts:
                self.session_message_counts[channel_id] = 0
            self.session_message_counts[channel_id] += 1
            
            # DB 전체 메시지 카운트 증가
            await self._increment_message_count(guild_id)
            
        except discord.Forbidden:
            logger.error(f"⚠️ 쓰레드 쓰기 권한 없음: {guild_id}")
        except discord.HTTPException as e:
            logger.error(f"⚠️ 쓰레드 메시지 전송 실패: {e}")
        except Exception as e:
            logger.error(f"⚠️ 쓰레드 기록 오류: {e}", exc_info=True)

    async def _create_edge_tts_file(self, text: str, guild_id: str, voice_override: str = None, user_id: str = None) -> Optional[str]:
        """Edge TTS 파일 생성 (개인 설정 우선 적용)"""
        try:
            # 설정 우선순위:
            # 1순위: voice_override (명령어에서 직접 지정)
            # 2순위: 개인 설정 (user_id가 있을 때)
            # 3순위: 서버 기본 설정
            
            selected_voice = None
            rate = '+0%'
            pitch = '+0Hz'
            volume = '+0%'
            
            if voice_override:
                # 명령어로 직접 지정한 경우
                selected_voice = voice_override
                # 서버 기본 속도/피치 사용
                settings = self.tts_settings.get(guild_id, {
                    'rate': '+0%',
                    'pitch': '+0Hz',
                    'volume': '+0%'
                })
                rate = settings.get('rate', '+0%')
                pitch = settings.get('pitch', '+0Hz')
                volume = '+50%'  # 고정값
                
            elif user_id:
                # 개인 설정 조회
                preference = await self.bot.db_manager.get_user_tts_preference(guild_id, user_id)
                if preference:
                    selected_voice = preference['voice']
                    rate = preference.get('rate', '+0%')
                    pitch = preference.get('pitch', '+0Hz')
                    volume = '+50%'  # 고정값
                    logger.info(f"👤 개인 설정 적용: {user_id} -> {selected_voice}")
            
            # 개인 설정이 없으면 서버 기본값
            if not selected_voice:
                settings = self.tts_settings.get(guild_id, {
                    'voice': '인준',
                    'rate': '+0%',
                    'pitch': '+0Hz',
                    'volume': '+0%'
                })
                selected_voice = settings['voice']
                rate = settings['rate']
                pitch = settings['pitch']
                volume = '+50%'
            
            # 통합 딕셔너리에서 가져오기
            voice_config = self.all_voices.get(selected_voice)
            if not voice_config:
                logger.error(f"❌ 잘못된 목소리: {selected_voice}")
                return None
            
            # 임시 파일 생성
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time() * 1000000)
            audio_file = os.path.join(temp_dir, f"edge_tts_{guild_id}_{timestamp}.mp3")
            
            logger.info(
                f"🎵 TTS 생성: '{text[:30]}...' "
                f"(목소리: {selected_voice}, 언어: {voice_config['language']})"
            )
            
            # Edge TTS로 음성 생성
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_config['voice'],
                rate=rate,
                pitch=pitch,
                volume=volume
            )
            
            await communicate.save(audio_file)
            
            if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                logger.info(f"✅ TTS 생성 완료 ({selected_voice}, {voice_config['language']})")
                return audio_file
            else:
                logger.error(f"❌ TTS 파일 생성 실패")
                return None
                
        except Exception as e:
            logger.error(f"❌ TTS 파일 생성 실패: {e}", exc_info=True)
            return None

    async def _play_audio_and_wait(self, voice_client: discord.VoiceClient, audio_file: str, text: str) -> bool:
        """오디오를 재생하고 완료될 때까지 대기 (큐 시스템용)"""
        try:
            logger.info(f"🔊 오디오 재생 시작: {os.path.basename(audio_file)}")
            
            # Linux 서버용 FFmpeg 옵션
            ffmpeg_options = '-vn -filter:a "volume=1.5"'
            
            # Discord PCM 오디오 소스 생성
            audio_source = discord.FFmpegPCMAudio(
                audio_file,
                executable=self.ffmpeg_executable,
                options=ffmpeg_options
            )
            
            # 재생 완료 추적
            play_finished = asyncio.Event()
            play_error = None
            
            def after_play(error):
                nonlocal play_error
                if error:
                    play_error = error
                    logger.error(f"⏸️ 재생 오류: {error}")
                else:
                    logger.info("✅ 오디오 재생 완료")
                play_finished.set()
                
                # 안전한 파일 정리
                try:
                    if self.bot.loop and self.bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._cleanup_audio_file(audio_file), 
                            self.bot.loop
                        )
                    else:
                        try:
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                                logger.info(f"🗑️ 동기 파일 삭제: {os.path.basename(audio_file)}")
                        except Exception as sync_error:
                            logger.error(f"⏸️ 동기 파일 삭제 오류: {sync_error}")
                except Exception as cleanup_error:
                    logger.error(f"⚠️ 파일 정리 실패: {cleanup_error}")
            
            # 재생 시작
            voice_client.play(audio_source, after=after_play)
            
            # 재생 시작 확인
            await asyncio.sleep(0.5)
            if not voice_client.is_playing():
                logger.warning("⏸️ 재생이 시작되지 않음")
                return False
            
            logger.info("🎵 오디오 재생 중...")
            
            # 재생 완료 대기 (최대 30초)
            try:
                await asyncio.wait_for(play_finished.wait(), timeout=30.0)
                success = play_error is None
                
                if success:
                    logger.info("✅ 오디오 재생 성공")
                else:
                    logger.error(f"⏸️ 재생 중 오류: {play_error}")
                
                return success
                
            except asyncio.TimeoutError:
                logger.warning("⚠️ 재생 타임아웃")
                voice_client.stop()
                return False
            
        except Exception as e:
            logger.error(f"⏸️ 오디오 재생 실패: {e}", exc_info=True)
            return False

    async def _can_send_in_channel(self, channel: discord.TextChannel) -> bool:
        """채널에 메시지를 보낼 수 있는지 확인"""
        if not isinstance(channel, discord.TextChannel):
            return False
        
        bot_permissions = channel.permissions_for(channel.guild.me)
        return bot_permissions.send_messages and bot_permissions.embed_links

    async def _play_audio_fixed(self, voice_client: discord.VoiceClient, audio_file: str, text: str) -> bool:
        """Linux 서버용 오디오 재생"""
        try:
            logger.info(f"🔊 Linux 서버 오디오 재생 시작: {os.path.basename(audio_file)}")
            
            # Linux 서버용 FFmpeg 옵션
            ffmpeg_options = '-vn -filter:a "volume=1.5"'
            
            # Discord PCM 오디오 소스 생성
            audio_source = discord.FFmpegPCMAudio(
                audio_file,
                executable=self.ffmpeg_executable,
                options=ffmpeg_options
            )
            
            # 재생 완료 추적
            play_finished = asyncio.Event()
            play_error = None
            
            def after_play(error):
                nonlocal play_error
                if error:
                    play_error = error
                    logger.error(f"⌛ 재생 오류: {error}")
                else:
                    logger.info("✅ 오디오 재생 완료")
                play_finished.set()
                
                # 안전한 파일 정리
                try:
                    if self.bot.loop and self.bot.loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._cleanup_audio_file(audio_file), 
                            self.bot.loop
                        )
                    else:
                        try:
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                                logger.info(f"🗑️ 동기 파일 삭제: {os.path.basename(audio_file)}")
                        except Exception as sync_error:
                            logger.error(f"⌛ 동기 파일 삭제 오류: {sync_error}")
                except Exception as cleanup_error:
                    logger.error(f"⚠️ 파일 정리 실패: {cleanup_error}")
            
            # 재생 시작
            voice_client.play(audio_source, after=after_play)
            
            # 재생 시작 확인
            await asyncio.sleep(0.5)
            if not voice_client.is_playing():
                logger.warning("⌛ 재생이 시작되지 않음")
                return False
            
            logger.info("🎵 오디오 재생 중...")
            
            # 재생 완료 대기
            try:
                await asyncio.wait_for(play_finished.wait(), timeout=30.0)
                success = play_error is None
                
                if success:
                    logger.info("✅ 오디오 재생 성공")
                else:
                    logger.error(f"⌛ 재생 중 오류: {play_error}")
                
                return success
                
            except asyncio.TimeoutError:
                logger.warning("⚠️ 재생 타임아웃")
                voice_client.stop()
                return False
            
        except Exception as e:
            logger.error(f"⌛ 오디오 재생 실패: {e}", exc_info=True)
            return False

    def _is_emoji_only(self, text: str) -> bool:
        """텍스트가 이모지만 포함하는지 확인"""
        import re
        # 한글, 영문, 숫자, 기본 특수문자 제거
        clean_text = re.sub(r'[a-zA-Z0-9가-힣ㄱ-ㅎㅏ-ㅣ\s\.,!?]', '', text)
        # 남은 게 있으면 이모지로 간주
        return len(clean_text.strip()) > 0 and len(text.strip().replace(clean_text, '').strip()) == 0

    def _should_process_auto_tts(
        self, 
        message: discord.Message, 
        settings: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        자동 TTS 처리 여부 판단
        
        Returns:
            (처리여부, 실패사유)
        """
        # 봇 메시지 필터링
        if message.author.bot and settings.get('filter_bot', True):
            return False, "봇 메시지"
        
        # 명령어는 처리하지 않음
        if message.content.startswith('/') or message.content.startswith('!'):
            return False, "명령어"
        
        text = message.content.strip()
        
        # 짧은 메시지 필터링
        if settings.get('filter_short', True):
            min_length = settings.get('min_length', 2)
            if len(text) < min_length:
                return False, f"{min_length}글자 미만"
        
        # 이모지만 있는 메시지 필터링
        if settings.get('filter_emoji', True):
            if self._is_emoji_only(text):
                return False, "이모지만 포함"
        
        # URL만 있는 메시지 필터링
        if text.startswith('http://') or text.startswith('https://'):
            return False, "URL만 포함"
        
        return True, None

    async def _get_user_voice_channel(self, guild: discord.Guild, user_id: str) -> Optional[discord.VoiceChannel]:
        """사용자가 현재 있는 음성 채널 반환"""
        member = guild.get_member(int(user_id))
        if member and member.voice:
            return member.voice.channel
        return None

    async def _cleanup_audio_file(self, audio_file: str):
        """오디오 파일 비동기 정리"""
        try:
            await asyncio.sleep(1)
            if os.path.exists(audio_file):
                os.remove(audio_file)
                logger.info(f"🗑️ 비동기 파일 삭제: {os.path.basename(audio_file)}")
        except Exception as e:
            logger.error(f"⌛ 비동기 파일 삭제 오류: {e}")

    async def _cleanup_channel(self, channel_id: str):
        """특정 채널의 모든 리소스 정리"""
        try:
            # 채널 정보 저장 (종료 로그용)
            guild_id = None
            voice_channel_name = "Unknown"
            
            if channel_id in self.voice_clients:
                voice_client = self.voice_clients[channel_id]
                guild_id = str(voice_client.guild.id)
                voice_channel_name = voice_client.channel.name
            
            # 큐 프로세서 중지
            if channel_id in self.queue_processors:
                self.queue_processors[channel_id].cancel()
                try:
                    await self.queue_processors[channel_id]
                except asyncio.CancelledError:
                    pass
                del self.queue_processors[channel_id]
            
            # 큐 정리
            if channel_id in self.tts_queues:
                del self.tts_queues[channel_id]
            
            # 세션 종료 로그
            if guild_id:
                await self._log_session_end(guild_id, voice_channel_name, channel_id)
            
            # VoiceClient 정리
            if channel_id in self.voice_clients:
                voice_client = self.voice_clients[channel_id]
                
                if voice_client.is_playing():
                    voice_client.stop()
                    await asyncio.sleep(0.3)
                
                if voice_client.is_connected():
                    await voice_client.disconnect()
                
                del self.voice_clients[channel_id]
            
            logger.info(f"✅ 채널 리소스 정리 완료: {channel_id}")
            
        except Exception as e:
            logger.error(f"⚠️ 채널 정리 중 오류: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        TTS 전용 채널에서 자동 TTS 처리
        """
        # 기본 필터링
        if not message.guild:
            return
        
        if message.author.bot:
            return  # 봇 메시지는 일단 여기서 걸러짐
        
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)
        
        # 🔍 디버그 1: 메시지 수신 확인
        logger.info(f"📩 [TTS-AUTO] 메시지 수신: '{message.content[:50]}' from {message.author.name} in #{message.channel.name}")
        
        # TTS 전용 채널 설정 조회
        settings = await self.bot.db_manager.get_tts_channel_settings(guild_id)
        
        # 🔍 디버그 2: 설정 확인
        logger.info(f"⚙️ [TTS-AUTO] TTS 채널 설정: {settings}")
        
        if not settings or not settings.get('channel_id'):
            logger.info(f"❌ [TTS-AUTO] TTS 전용 채널 미설정 - 서버: {message.guild.name}")
            return  # 전용 채널 미설정
        
        # 🔍 디버그 3: 채널 ID 비교
        logger.info(f"🔍 [TTS-AUTO] 현재 채널: {channel_id}, 설정된 채널: {settings['channel_id']}, 일치: {settings['channel_id'] == channel_id}")
        
        # 전용 채널이 아니면 무시
        if settings['channel_id'] != channel_id:
            logger.debug(f"[TTS-AUTO] 다른 채널의 메시지 (무시) - #{message.channel.name}")
            return
        
        logger.info(f"✅ [TTS-AUTO] TTS 전용 채널 확인됨: #{message.channel.name}")
        
        # 메시지 필터링 체크
        should_process, reason = self._should_process_auto_tts(message, settings)
        
        # 🔍 디버그 4: 필터링 결과
        logger.info(f"🔍 [TTS-AUTO] 필터링 결과: {should_process}, 사유: {reason}")
        
        if not should_process:
            logger.info(f"🚫 [TTS-AUTO] 자동 TTS 스킵: {reason} - '{message.content[:20]}'")
            return
        
        logger.info(f"✅ [TTS-AUTO] 필터링 통과: '{message.content[:30]}'")
        
        # 사용자가 음성 채널에 있는지 확인
        user_voice_channel = await self._get_user_voice_channel(message.guild, str(message.author.id))
        
        # 🔍 디버그 5: 사용자 음성 채널 확인
        if user_voice_channel:
            logger.info(f"✅ [TTS-AUTO] 사용자 음성 채널: {user_voice_channel.name} (ID: {user_voice_channel.id})")
        else:
            logger.warning(f"❌ [TTS-AUTO] 사용자가 음성 채널에 없음: {message.author.name}")
            logger.warning(f"   ⚠️ 해결방법: 사용자가 먼저 음성 채널에 입장해야 합니다!")
        
        if not user_voice_channel:
            # 조용히 무시 (사용자가 음성 채널에 없음)
            return
        
        user_channel_id = str(user_voice_channel.id)
        
        # 🔍 디버그 6: 봇 연결 상태 확인
        logger.info(f"🔍 [TTS-AUTO] 현재 봇이 연결된 채널들: {list(self.voice_clients.keys())}")
        logger.info(f"🔍 [TTS-AUTO] 사용자가 있는 채널 ID: {user_channel_id}")
        logger.info(f"🔍 [TTS-AUTO] 봇이 사용자 채널에 연결됨: {user_channel_id in self.voice_clients}")
        
        # 해당 음성 채널에 봇이 연결되어 있는지 확인
        if user_channel_id not in self.voice_clients:
            logger.warning(f"❌ [TTS-AUTO] 봇이 사용자 채널에 연결되지 않음")
            logger.warning(f"   ⚠️ 사용자 채널: {user_voice_channel.name} (ID: {user_channel_id})")
            logger.warning(f"   ⚠️ 봇이 연결된 채널: {[self.voice_clients[cid].channel.name for cid in self.voice_clients.keys()] if self.voice_clients else '없음'}")
            logger.warning(f"   ⚠️ 해결방법: 사용자가 있는 채널에서 `/입장` 명령어를 사용하세요!")
            
            # 봇이 연결되지 않음 - 안내 메시지
            embed = discord.Embed(
                title="🎤 TTS 봇이 연결되지 않음",
                description=f"**{user_voice_channel.name}**에 먼저 `/입장` 해주세요!",
                color=0xff9900
            )
            await message.channel.send(embed=embed, delete_after=5)
            return
        
        logger.info(f"✅ [TTS-AUTO] 봇이 사용자 채널에 연결되어 있음!")
        
        voice_client = self.voice_clients[user_channel_id]
        
        if not voice_client.is_connected():
            logger.warning(f"❌ [TTS-AUTO] 봇 연결이 끊어짐")
            return
        
        logger.info(f"✅ [TTS-AUTO] 봇 음성 연결 정상")
        
        # TTS 큐에 추가
        text = message.content.strip()
        user_id = str(message.author.id)
        
        # 개인 설정 조회 (목소리 결정용)
        preference = await self.bot.db_manager.get_user_tts_preference(guild_id, user_id)
        selected_voice = preference['voice'] if preference else self.tts_settings.get(guild_id, {}).get('voice', '인준')
        
        logger.info(f"🎤 [TTS-AUTO] 선택된 목소리: {selected_voice}")
        
        tts_request = {
            'user': message.author,
            'user_id': user_id,
            'text': text,
            'voice': selected_voice,
            'timestamp': time.time(),
            'channel_name': user_voice_channel.name,
            'channel_id': user_channel_id,
            'auto_tts': True  # 자동 TTS 플래그
        }
        
        await self.tts_queues[user_channel_id].put(tts_request)
        queue_size = self.tts_queues[user_channel_id].qsize()
        
        logger.info(f"✅ [TTS-AUTO] TTS 큐에 추가 완료: 대기열 {queue_size}번째")
        
        # 반응 추가 (처리 중 표시)
        try:
            await message.add_reaction('🎵')
            logger.info(f"✅ [TTS-AUTO] 메시지에 반응 추가 완료")
        except discord.Forbidden:
            logger.warning(f"⚠️ [TTS-AUTO] 반응 추가 권한 없음")
            pass
        
        logger.info(
            f"🎵 [TTS-AUTO] 자동 TTS 큐 추가 완료: {message.author.display_name} > "
            f"'{text[:30]}...' (대기: {queue_size})"
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """음성 상태 변경 감지 (채널별로 봇이 혼자 남았을 때 자동 퇴장)"""
        if member == self.bot.user:
            return  # 봇 자신의 상태 변경은 무시
        
        # 봇이 연결된 모든 채널 확인
        for channel_id, voice_client in list(self.voice_clients.items()):
            if not voice_client.is_connected():
                continue
            
            bot_channel = voice_client.channel
            
            # 이 채널에서 멤버 상태 변경이 있었는지 확인
            if before.channel == bot_channel or after.channel == bot_channel:
                # 현재 채널의 사람 수 확인
                human_members = [m for m in bot_channel.members if not m.bot]
                
                # 사람이 아무도 없으면 10초 후 자동 퇴장
                if len(human_members) == 0:
                    logger.info(f"💤 채널에 사람이 없음, 10초 후 자동 퇴장: {bot_channel.name}")
                    await asyncio.sleep(10)
                    
                    # 10초 후에도 여전히 혼자인지 재확인
                    if voice_client.is_connected():
                        current_human_members = [m for m in voice_client.channel.members if not m.bot]
                        if len(current_human_members) == 0:
                            try:
                                logger.info(f"🚪 자동 퇴장 실행: {bot_channel.name}")
                                await self._cleanup_channel(channel_id)
                                logger.info(f"✅ 자동 퇴장 완료: {bot_channel.name}")
                            except Exception as e:
                                logger.error(f"❌ 자동 퇴장 오류: {e}")

async def setup(bot):
    """Linux 서버용 TTS Commands Cog를 봇에 추가"""
    await bot.add_cog(TTSCommands(bot))
    logger.info("🎤 Linux 서버용 TTS Commands 시스템이 로드되었습니다!")