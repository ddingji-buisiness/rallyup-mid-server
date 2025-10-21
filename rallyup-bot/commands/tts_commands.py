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

class TTSCommands(commands.Cog):
    """Linux 서버용 TTS Commands (Opus 경로 수정)"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients: Dict[str, discord.VoiceClient] = {}
        self.tts_settings: Dict[str, Dict[str, Any]] = {}
        
        # 확장된 한국어 음성 옵션
        self.korean_voices = {
            'injoon': {
                'voice': 'ko-KR-InJoonNeural',
                'name': '인준 (남성, 친근한)',
                'gender': '남성',
                'style': '친근한'
            },
            'sunhi': {
                'voice': 'ko-KR-SunHiNeural', 
                'name': '선희 (여성, 밝은)',
                'gender': '여성',
                'style': '밝은'
            },
            'hyunsu': {
                'voice': 'ko-KR-HyunsuNeural',
                'name': '현수 (남성, 차분한)',
                'gender': '남성', 
                'style': '차분한'
            },
            'gookmin': {
                'voice': 'ko-KR-GookMinNeural',
                'name': '국민 (남성, 표준어)',
                'gender': '남성',
                'style': '표준어'
            },
            'youngmee': {
                'voice': 'ko-KR-YeongMiNeural',
                'name': '영미 (여성, 상냥한)',
                'gender': '여성',
                'style': '상냥한'
            }
        }
        
        # FFmpeg 경로 설정
        self.ffmpeg_executable = self._find_ffmpeg()
        
        # 서버 환경용 Opus 로딩
        self._force_load_opus_linux()

    def _find_ffmpeg(self):
        """FFmpeg 경로 찾기 (Linux 서버용)"""
        paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS 호환
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

    @app_commands.command(name="입장", description="TTS 봇을 음성 채널에 입장시킵니다")
    async def tts_join(self, interaction: discord.Interaction):
        """TTS 봇 음성 채널 입장"""
        
        # Opus 확인
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
        guild_id = str(interaction.guild.id)
        
        try:
            # 기존 연결 확인
            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
                current_channel = self.voice_clients[guild_id].channel
                if current_channel.id == channel.id:
                    embed = discord.Embed(
                        title="ℹ️ 이미 연결됨",
                        description=f"이미 **{channel.name}**에 연결되어 있습니다!",
                        color=0x0099ff
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                else:
                    await self.voice_clients[guild_id].move_to(channel)
                    embed = discord.Embed(
                        title="🔄 채널 이동",
                        description=f"**{channel.name}**으로 이동했습니다!",
                        color=0x00ff00
                    )
                    await interaction.response.send_message(embed=embed)
                    return
            
            await interaction.response.defer()
            
            # 음성 채널 연결
            voice_client = await channel.connect(timeout=10.0, reconnect=True)
            self.voice_clients[guild_id] = voice_client
            
            # 기본 설정 초기화
            if guild_id not in self.tts_settings:
                self.tts_settings[guild_id] = {
                    'voice': 'injoon',
                    'rate': '+0%',
                    'pitch': '+0Hz',
                    'volume': '+0%',
                    'last_used': time.time()
                }
                logger.info(f"🆕 새 서버 TTS 설정 초기화: {interaction.guild.name}")
            else:
                self.tts_settings[guild_id]['last_used'] = time.time()
            
            # 연결 안정화 대기
            await asyncio.sleep(0.5)
            
            if not voice_client.is_connected():
                await interaction.followup.send("⌛ 음성 연결에 실패했습니다.")
                return
            
            # 성공 메시지
            current_voice = self.tts_settings[guild_id]['voice']
            voice_info = self.korean_voices[current_voice]
            
            embed = discord.Embed(
                title="🎤 TTS 봇 입장 완료",
                description=f"**{channel.name}**에 입장했습니다!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="🔧 시스템 상태",
                value=f"🎵 Edge TTS: ✅ 정상\n"
                      f"⚙️ Opus: ✅ 로드됨\n"
                      f"🖥️ 서버: Linux\n"
                      f"📶 지연시간: {voice_client.latency*1000:.1f}ms\n"
                      f"🎭 현재 목소리: {voice_info['name']}",
                inline=False
            )
            
            embed.add_field(
                name="📖 사용법",
                value="`/말하기 <내용> [목소리]` - 텍스트를 음성으로 변환\n"
                      "`/볼륨설정 <속도> [피치]` - 목소리 설정 조절\n"
                      "`/현재볼륨` - 현재 설정 확인\n"
                      "`/퇴장` - 음성 채널에서 퇴장",
                inline=False
            )
            
            embed.set_footer(text="💡 팁: /말하기 명령어에서 목소리를 선택할 수 있습니다!")
            
            await interaction.followup.send(embed=embed)
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
        목소리: Optional[Literal['injoon', 'sunhi', 'hyunsu', 'gookmin', 'youngmee']] = None
    ):
        """메인 TTS 명령어 (목소리 선택 기능 포함)"""
        guild_id = str(interaction.guild.id)
        
        # 입력 검증
        if not 내용 or len(내용.strip()) == 0:
            await interaction.response.send_message("⌛ 텍스트를 입력해주세요!", ephemeral=True)
            return
            
        if len(내용) > 1000:
            await interaction.response.send_message("⌛ 텍스트는 1000자 이하로 입력해주세요!", ephemeral=True)
            return
        
        # 봇 연결 확인
        if guild_id not in self.voice_clients:
            await interaction.response.send_message("⌛ 먼저 `/입장` 명령어를 사용해주세요!", ephemeral=True)
            return
            
        voice_client = self.voice_clients[guild_id]
        if not voice_client.is_connected():
            await interaction.response.send_message("⌛ 음성 연결이 끊어졌습니다. `/입장`을 다시 해주세요!", ephemeral=True)
            return
        
        # 목소리 설정 결정
        selected_voice = 목소리 if 목소리 else self.tts_settings.get(guild_id, {}).get('voice', 'injoon')
        voice_info = self.korean_voices[selected_voice]
        
        # 흔적 안남김 (목소리 정보 포함)
        await interaction.response.send_message(
            f"🔊 재생 중... (목소리: {voice_info['name']})",
            ephemeral=True,
            delete_after=3
        )
        
        try:
            # 기존 재생 중지
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.3)
            
            # Edge TTS 파일 생성 (선택된 목소리로)
            audio_file = await self._create_edge_tts_file(내용, guild_id, selected_voice)
            
            if not audio_file:
                await interaction.followup.send("⌛ TTS 생성 실패", ephemeral=True)
                return
            
            # 오디오 재생
            success = await self._play_audio_fixed(voice_client, audio_file, 내용)
            
            # 로그만 기록
            if success:
                logger.info(f"🔊 TTS 성공: {interaction.user.display_name} > '{내용[:50]}' (목소리: {selected_voice})")
            else:
                await interaction.followup.send("⌛ 재생 실패", ephemeral=True)
            
        except Exception as e:
            logger.error(f"⌛ TTS 오류: {e}", exc_info=True)
            await interaction.followup.send(f"⌛ 오류: {str(e)}", ephemeral=True)

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
                'voice': 'injoon',
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
        """현재 TTS 설정 확인"""
        guild_id = str(interaction.guild.id)
        
        embed = discord.Embed(
            title="🔊 현재 TTS 설정",
            color=0x0099ff
        )
        
        # 봇 연결 상태
        if guild_id in self.voice_clients:
            vc = self.voice_clients[guild_id]
            if vc.is_connected():
                embed.add_field(
                    name="🤖 봇 상태",
                    value=f"연결: ✅ {vc.channel.name}\n"
                          f"지연: {vc.latency*1000:.1f}ms\n"
                          f"재생: {'🔊' if vc.is_playing() else '⏹️'}",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🤖 봇 상태",
                    value="연결: ❌ 연결 끊어짐",
                    inline=True
                )
        else:
            embed.add_field(
                name="🤖 봇 상태",
                value="연결: ❌ 미연결\n먼저 `/입장`을 해주세요",
                inline=True
            )
        
        # TTS 설정
        if guild_id in self.tts_settings:
            settings = self.tts_settings[guild_id]
            current_voice = settings['voice']
            voice_info = self.korean_voices[current_voice]
            
            embed.add_field(
                name="🎭 음성 설정",
                value=f"목소리: {voice_info['name']}\n"
                      f"성별: {voice_info['gender']}\n"
                      f"스타일: {voice_info['style']}",
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
        
        # 사용 가능한 목소리 목록
        voice_list = []
        for key, info in self.korean_voices.items():
            voice_list.append(f"• **{key}**: {info['name']}")
        
        embed.add_field(
            name="🎵 사용 가능한 목소리",
            value="\n".join(voice_list),
            inline=False
        )
        
        embed.add_field(
            name="📖 사용법",
            value="`/말하기 안녕하세요 sunhi` - 선희 목소리로 재생\n"
                  "`/볼륨설정 +20 -10` - 속도 빠르게, 피치 낮게",
            inline=False
        )
        
        embed.set_footer(text="💡 각 명령어마다 다른 목소리를 선택할 수 있습니다!")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="퇴장", description="TTS 봇을 음성 채널에서 퇴장시킵니다")
    async def tts_leave(self, interaction: discord.Interaction):
        """TTS 봇 음성 채널 퇴장"""
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.voice_clients:
            embed = discord.Embed(
                title="ℹ️ 연결되지 않음",
                description="봇이 음성 채널에 연결되어 있지 않습니다.",
                color=0x0099ff
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            voice_client = self.voice_clients[guild_id]
            channel_name = voice_client.channel.name
            
            # 재생 중지
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.3)
            
            # 연결 해제
            await voice_client.disconnect()
            
            # 정리
            del self.voice_clients[guild_id]
            
            # 성공 메시지
            embed = discord.Embed(
                title="👋 TTS 봇 퇴장",
                description=f"**{channel_name}**에서 퇴장했습니다.",
                color=0x00ff00
            )
            embed.set_footer(text="다시 사용하려면 /입장 명령어를 사용해주세요!")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"👋 TTS 봇 퇴장: {interaction.guild.name} > {channel_name}")
            
        except Exception as e:
            embed = discord.Embed(
                title="⌛ 퇴장 실패",
                description=f"퇴장 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            logger.error(f"⌛ TTS 퇴장 오류: {e}", exc_info=True)

    async def _create_edge_tts_file(self, text: str, guild_id: str, voice_override: str = None) -> Optional[str]:
        """Edge TTS 파일 생성 (목소리 선택 지원)"""
        try:
            settings = self.tts_settings.get(guild_id, {
                'voice': 'injoon',
                'rate': '+0%',
                'pitch': '+0Hz',
                'volume': '+0%'
            })
            
            # 목소리 오버라이드가 있으면 사용, 없으면 서버 설정 사용
            selected_voice = voice_override if voice_override else settings['voice']
            voice_config = self.korean_voices[selected_voice]
            
            # 임시 파일 생성
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time() * 1000000)
            audio_file = os.path.join(temp_dir, f"edge_tts_{guild_id}_{timestamp}.mp3")
            
            logger.info(f"🎵 TTS 생성: '{text}' (목소리: {selected_voice})")
            
            # Edge TTS로 음성 생성
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_config['voice'],
                rate=settings['rate'],
                pitch=settings['pitch'],
                volume='+50%'  # 적절한 볼륨
            )
            
            await communicate.save(audio_file)
            
            if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                logger.info(f"✅ TTS 생성 완료 ({selected_voice})")
                return audio_file
            else:
                logger.error(f"⌛ TTS 파일 생성 실패")
                return None
                
        except Exception as e:
            logger.error(f"⌛ TTS 파일 생성 실패: {e}", exc_info=True)
            return None

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

    async def _cleanup_audio_file(self, audio_file: str):
        """오디오 파일 비동기 정리"""
        try:
            await asyncio.sleep(1)
            if os.path.exists(audio_file):
                os.remove(audio_file)
                logger.info(f"🗑️ 비동기 파일 삭제: {os.path.basename(audio_file)}")
        except Exception as e:
            logger.error(f"⌛ 비동기 파일 삭제 오류: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """음성 상태 변경 감지 (봇이 혼자 남았을 때 자동 퇴장)"""
        if member == self.bot.user:
            return  # 봇 자신의 상태 변경은 무시
        
        guild_id = str(member.guild.id)
        
        # 봇이 연결된 서버인지 확인
        if guild_id not in self.voice_clients:
            return
        
        voice_client = self.voice_clients[guild_id]
        if not voice_client.is_connected():
            return
        
        # 봇이 있는 채널의 멤버 수 확인
        bot_channel = voice_client.channel
        human_members = [m for m in bot_channel.members if not m.bot]
        
        # 사람이 아무도 없으면 10초 후 자동 퇴장
        if len(human_members) == 0:
            logger.info(f"👤 채널에 사람이 없음, 10초 후 자동 퇴장: {bot_channel.name}")
            await asyncio.sleep(10)
            
            # 10초 후에도 여전히 혼자인지 재확인
            if voice_client.is_connected():
                current_human_members = [m for m in voice_client.channel.members if not m.bot]
                if len(current_human_members) == 0:
                    try:
                        if voice_client.is_playing():
                            voice_client.stop()
                        await voice_client.disconnect()
                        del self.voice_clients[guild_id]
                        
                        logger.info(f"🚪 자동 퇴장 완료: {bot_channel.name}")
                    except Exception as e:
                        logger.error(f"⌛ 자동 퇴장 오류: {e}")

async def setup(bot):
    """Linux 서버용 TTS Commands Cog를 봇에 추가"""
    await bot.add_cog(TTSCommands(bot))
    logger.info("🎤 Linux 서버용 TTS Commands 시스템이 로드되었습니다!")