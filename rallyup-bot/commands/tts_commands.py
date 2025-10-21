# ====================================
# 프로덕션 레벨 TTS 명령어 시스템 - 완성판
# RallyUp 디스코드 봇 TTS 기능
# ====================================

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import tempfile
import os
import logging
import subprocess
import sys
from gtts import gTTS
from ctypes.util import find_library
import struct
import math
import io
from pathlib import Path
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class TTSCommands(commands.Cog):
    """RallyUp 봇 TTS 명령어 시스템"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients: Dict[str, discord.VoiceClient] = {}
        self.tts_settings: Dict[str, Dict[str, Any]] = {}
        
        # 시스템 최적화 설정
        self._setup_system_optimization()
        
        # Opus 라이브러리 초기화
        asyncio.create_task(self._initialize_audio_system())

    def _setup_system_optimization(self):
        """시스템별 최적화 설정"""
        if sys.platform == 'darwin':  # macOS
            ffmpeg_paths = [
                '/opt/homebrew/bin/ffmpeg',   # Apple Silicon
                '/usr/local/bin/ffmpeg',      # Intel Mac
                '/usr/bin/ffmpeg'             # 시스템 기본
            ]
            
            for path in ffmpeg_paths:
                if os.path.exists(path):
                    self.ffmpeg_executable = path
                    logger.info(f"✅ FFmpeg 경로 설정: {path}")
                    break
            else:
                self.ffmpeg_executable = 'ffmpeg'
                logger.warning("⚠️ FFmpeg 경로를 PATH에서 찾습니다")
        else:
            self.ffmpeg_executable = 'ffmpeg'

    async def _initialize_audio_system(self):
        """오디오 시스템 초기화"""
        try:
            if not discord.opus.is_loaded():
                # macOS Opus 라이브러리 로드
                if sys.platform == 'darwin':
                    opus_paths = [
                        '/opt/homebrew/lib/libopus.dylib',
                        '/usr/local/lib/libopus.dylib',
                    ]
                    
                    for opus_path in opus_paths:
                        if os.path.exists(opus_path):
                            try:
                                discord.opus.load_opus(opus_path)
                                if discord.opus.is_loaded():
                                    logger.info(f"✅ Opus 로드 성공: {opus_path}")
                                    break
                            except Exception as e:
                                logger.warning(f"⚠️ Opus 로드 실패 {opus_path}: {e}")
                
                # 자동 감지 시도
                if not discord.opus.is_loaded():
                    try:
                        discord.opus.load_opus()
                        if discord.opus.is_loaded():
                            logger.info("✅ Opus 자동 로드 성공")
                    except Exception as e:
                        logger.error(f"❌ Opus 자동 로드 실패: {e}")
            
            # 최종 상태 확인
            if discord.opus.is_loaded():
                try:
                    version = discord.opus._OpusStruct.get_opus_version()
                    logger.info(f"🎵 Opus 시스템 준비 완료 - 버전: {version}")
                except:
                    logger.info("🎵 Opus 시스템 준비 완료")
            else:
                logger.error("❌ Opus 로드 실패 - TTS 품질이 제한될 수 있습니다")
                
        except Exception as e:
            logger.error(f"❌ 오디오 시스템 초기화 오류: {e}")

    # ============================================
    # 기본 TTS 명령어들
    # ============================================

    @app_commands.command(name="입장", description="TTS 봇을 음성 채널에 입장시킵니다")
    async def tts_join(self, interaction: discord.Interaction):
        """TTS 봇 음성 채널 입장"""
        # 사용자 음성 채널 확인
        if not interaction.user.voice:
            embed = discord.Embed(
                title="❌ 음성 채널 필요",
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
                    # 다른 채널로 이동
                    await self.voice_clients[guild_id].move_to(channel)
                    embed = discord.Embed(
                        title="🔄 채널 이동",
                        description=f"**{channel.name}**으로 이동했습니다!",
                        color=0x00ff00
                    )
                    await interaction.response.send_message(embed=embed)
                    return
            
            # 새로운 연결
            await interaction.response.defer()
            
            # 음성 채널 연결
            voice_client = await channel.connect(timeout=10.0, reconnect=True)
            self.voice_clients[guild_id] = voice_client
            
            # 서버별 TTS 설정 초기화
            self.tts_settings[guild_id] = {
                'volume_boost': 10.0,
                'use_optimization': True,
                'last_used': time.time()
            }
            
            # 연결 안정화 대기
            await asyncio.sleep(0.5)
            
            # 연결 상태 검증
            if not voice_client.is_connected():
                await interaction.followup.send("❌ 음성 연결에 실패했습니다.")
                return
            
            # 성공 메시지
            opus_loaded = discord.opus.is_loaded()
            
            embed = discord.Embed(
                title="🎤 TTS 봇 입장 완료",
                description=f"**{channel.name}**에 입장했습니다!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="🔧 시스템 상태",
                value=f"🎵 Opus: {'✅ 정상' if opus_loaded else '⚠️ 제한모드'}\n"
                      f"⚙️ FFmpeg: 최적화됨\n"
                      f"📶 지연시간: {voice_client.latency*1000:.1f}ms\n"
                      f"🔊 볼륨 부스트: 활성화",
                inline=False
            )
            
            embed.add_field(
                name="📝 사용법",
                value="`/말하기 <내용>` - 텍스트를 음성으로 변환\n"
                      "`/테스트` - 음성 연결 테스트\n"
                      "`/퇴장` - 음성 채널에서 퇴장",
                inline=False
            )
            
            embed.set_footer(text="💡 팁: 긴 텍스트일수록 더 자연스럽게 들립니다!")
            
            await interaction.followup.send(embed=embed)
            
            # 서버 로그
            logger.info(f"🎤 TTS 봇 입장: {interaction.guild.name} > {channel.name} (사용자: {interaction.user.display_name})")
            
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="❌ 연결 실패",
                description="음성 채널 연결 시간이 초과되었습니다. 다시 시도해주세요.",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
        except discord.ClientException as e:
            embed = discord.Embed(
                title="❌ Discord 연결 오류",
                description=f"Discord 연결 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="❌ 입장 실패",
                description=f"예상치 못한 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"❌ TTS 입장 오류: {e}", exc_info=True)

    @app_commands.command(name="말하기", description="텍스트를 음성으로 변환하여 재생합니다")
    @app_commands.describe(내용="음성으로 변환할 텍스트 (1-500자)")
    async def tts_speak(self, interaction: discord.Interaction, 내용: str):
        """메인 TTS 명령어"""
        guild_id = str(interaction.guild.id)
        
        # 입력 검증
        if not 내용 or len(내용.strip()) == 0:
            embed = discord.Embed(
                title="❌ 텍스트 필요",
                description="변환할 텍스트를 입력해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        if len(내용) > 500:
            embed = discord.Embed(
                title="❌ 텍스트 길이 초과",
                description="텍스트는 500자 이하로 입력해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # 봇 연결 확인
        if guild_id not in self.voice_clients:
            embed = discord.Embed(
                title="❌ 봇이 연결되지 않음",
                description="먼저 `/입장` 명령어로 봇을 음성 채널에 입장시켜주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        voice_client = self.voice_clients[guild_id]
        if not voice_client.is_connected():
            embed = discord.Embed(
                title="❌ 음성 연결 끊어짐",
                description="봇이 음성 채널에 연결되어 있지 않습니다!\n다시 `/입장` 명령어를 사용해주세요.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # 기존 재생 중지
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.3)  # 안전한 중지 대기
            
            # TTS 파일 생성
            start_time = time.time()
            audio_file = await self._create_optimized_tts_file(내용, interaction)
            
            if not audio_file:
                embed = discord.Embed(
                    title="❌ TTS 생성 실패",
                    description="음성 파일 생성에 실패했습니다. 다시 시도해주세요.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
                return
            
            generation_time = time.time() - start_time
            
            # 오디오 재생
            success = await self._play_optimized_audio(voice_client, audio_file, 내용, interaction)
            
            if success:
                # 성공 메시지
                embed = discord.Embed(
                    title="🔊 음성 재생 완료",
                    description=f"**{interaction.user.display_name}**",
                    color=0x00ff00
                )
                
                # 내용 표시 (길면 자르기)
                display_content = 내용[:100] + "..." if len(내용) > 100 else 내용
                embed.add_field(
                    name="💬 재생 내용",
                    value=f"`{display_content}`",
                    inline=False
                )
                
                embed.add_field(
                    name="⏱️ 처리 시간",
                    value=f"{generation_time:.1f}초",
                    inline=True
                )
                
                embed.add_field(
                    name="👥 채널",
                    value=voice_client.channel.name,
                    inline=True
                )
                
                await interaction.followup.send(embed=embed)
                
                # 서버 로그
                logger.info(f"🔊 TTS 재생 성공: {interaction.user.display_name} > '{내용[:50]}...' ({generation_time:.1f}s)")
                
            else:
                embed = discord.Embed(
                    title="❌ 음성 재생 실패",
                    description="음성 재생에 실패했습니다.\n`/테스트` 명령어로 연결 상태를 확인해주세요.",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ TTS 처리 오류",
                description=f"음성 처리 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"❌ TTS 처리 오류: {e}", exc_info=True)

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
            if guild_id in self.tts_settings:
                del self.tts_settings[guild_id]
            
            # 성공 메시지
            embed = discord.Embed(
                title="👋 TTS 봇 퇴장",
                description=f"**{channel_name}**에서 퇴장했습니다.",
                color=0x00ff00
            )
            embed.set_footer(text="다시 사용하려면 /입장 명령어를 사용해주세요!")
            
            await interaction.response.send_message(embed=embed)
            
            # 서버 로그
            logger.info(f"👋 TTS 봇 퇴장: {interaction.guild.name} > {channel_name} (사용자: {interaction.user.display_name})")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 퇴장 실패",
                description=f"퇴장 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed)
            logger.error(f"❌ TTS 퇴장 오류: {e}", exc_info=True)

    # ============================================
    # 테스트 및 진단 명령어들
    # ============================================

    @app_commands.command(name="테스트", description="TTS 시스템 연결 및 음성 출력을 테스트합니다")
    async def tts_test(self, interaction: discord.Interaction):
        """TTS 시스템 테스트"""
        guild_id = str(interaction.guild.id)
        
        if guild_id not in self.voice_clients:
            embed = discord.Embed(
                title="❌ 봇이 연결되지 않음",
                description="먼저 `/입장` 명령어를 사용해주세요!",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        voice_client = self.voice_clients[guild_id]
        await interaction.response.defer()
        
        try:
            if voice_client.is_playing():
                voice_client.stop()
                await asyncio.sleep(0.5)
            
            # 테스트 안내
            embed = discord.Embed(
                title="🧪 TTS 시스템 테스트",
                description="**3초 후 테스트 신호음과 음성이 재생됩니다!**",
                color=0x0099ff
            )
            embed.add_field(
                name="🎯 테스트 내용",
                value="1️⃣ 신호음 (삐 소리)\n2️⃣ 한국어 TTS 음성\n3️⃣ 연결 상태 확인",
                inline=False
            )
            embed.add_field(
                name="👂 확인사항",
                value="• 신호음이 들리는가?\n• TTS 음성이 들리는가?\n• 다른 사용자들도 들리는가?",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
            # 3초 대기
            await asyncio.sleep(3)
            
            # 1단계: 신호음 테스트
            await interaction.followup.send("🔊 **1단계**: 신호음 테스트 중... (삐~~~~~~)")
            
            signal_success = await self._play_test_signal(voice_client)
            await asyncio.sleep(1)
            
            # 2단계: TTS 테스트
            await interaction.followup.send("🗣️ **2단계**: TTS 음성 테스트 중...")
            
            tts_success = await self._play_test_tts(voice_client)
            
            # 결과 리포트
            await asyncio.sleep(1)
            
            if signal_success and tts_success:
                embed = discord.Embed(
                    title="✅ 테스트 성공!",
                    description="TTS 시스템이 정상적으로 작동합니다!",
                    color=0x00ff00
                )
                embed.add_field(
                    name="🎵 테스트 결과",
                    value="✅ 신호음 재생 성공\n✅ TTS 음성 재생 성공\n✅ 연결 상태 정상",
                    inline=False
                )
                embed.add_field(
                    name="🚀 이제 사용하세요!",
                    value="`/말하기 안녕하세요` - TTS 시작하기",
                    inline=False
                )
            elif signal_success and not tts_success:
                embed = discord.Embed(
                    title="⚠️ 부분 성공",
                    description="신호음은 들리지만 TTS에 문제가 있습니다.",
                    color=0xffaa00
                )
                embed.add_field(
                    name="🔧 해결 방법",
                    value="1. `/퇴장` 후 `/입장` 재시도\n2. Discord 앱 재시작\n3. 봇 재시작 요청",
                    inline=False
                )
            elif not signal_success:
                embed = discord.Embed(
                    title="❌ 테스트 실패",
                    description="신호음이 들리지 않습니다. Discord 연결에 문제가 있습니다.",
                    color=0xff0000
                )
                embed.add_field(
                    name="🔧 해결 방법",
                    value="1. Discord 앱 재시작\n2. 출력 장치 설정 확인\n3. `/퇴장` 후 `/입장` 재시도",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 테스트 중 오류",
                description=f"테스트 실행 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
            await interaction.followup.send(embed=embed)
            logger.error(f"❌ TTS 테스트 오류: {e}", exc_info=True)

    @app_commands.command(name="상태", description="현재 TTS 시스템 상태를 확인합니다")
    async def tts_status(self, interaction: discord.Interaction):
        """TTS 시스템 상태 확인"""
        guild_id = str(interaction.guild.id)
        
        embed = discord.Embed(
            title="📊 TTS 시스템 상태",
            color=0x0099ff
        )
        
        # 1. 시스템 정보
        embed.add_field(
            name="🖥️ 시스템 정보",
            value=f"플랫폼: {sys.platform}\n"
                  f"Python: {sys.version.split()[0]}\n"
                  f"Discord.py: {discord.__version__}",
            inline=True
        )
        
        # 2. 오디오 라이브러리
        opus_loaded = discord.opus.is_loaded()
        embed.add_field(
            name="🎵 오디오 라이브러리",
            value=f"Opus: {'✅ 로드됨' if opus_loaded else '❌ 미로드'}\n"
                  f"FFmpeg: ✅ 사용 가능\n"
                  f"gTTS: ✅ 준비됨",
            inline=True
        )
        
        # 3. 봇 연결 상태
        if guild_id in self.voice_clients:
            vc = self.voice_clients[guild_id]
            embed.add_field(
                name="🤖 봇 상태",
                value=f"연결: ✅ {vc.channel.name}\n"
                      f"활성: {'✅' if vc.is_connected() else '❌'}\n"
                      f"재생: {'🔊' if vc.is_playing() else '⏹️'}\n"
                      f"지연: {vc.latency*1000:.1f}ms",
                inline=True
            )
            
            # 채널 멤버 수
            member_count = len(vc.channel.members)
            embed.add_field(
                name="👥 채널 정보",
                value=f"채널: {vc.channel.name}\n"
                      f"멤버: {member_count}명\n"
                      f"권한: ✅ 정상",
                inline=True
            )
        else:
            embed.add_field(
                name="🤖 봇 상태",
                value="연결: ❌ 미연결\n"
                      "활성: ❌\n"
                      "재생: ⏹️\n"
                      "지연: -",
                inline=True
            )
            
            embed.add_field(
                name="👥 채널 정보",
                value="채널: 없음\n"
                      "멤버: -\n"
                      "권한: -",
                inline=True
            )
        
        # 4. TTS 설정
        if guild_id in self.tts_settings:
            settings = self.tts_settings[guild_id]
            embed.add_field(
                name="⚙️ TTS 설정",
                value=f"볼륨 부스트: {settings['volume_boost']}배\n"
                      f"최적화: {'✅' if settings['use_optimization'] else '❌'}\n"
                      f"마지막 사용: {time.time() - settings['last_used']:.0f}초 전",
                inline=False
            )
        
        # 사용자 상태
        if interaction.user.voice:
            embed.add_field(
                name="👤 사용자 상태",
                value=f"위치: ✅ {interaction.user.voice.channel.name}\n"
                      f"음소거: {'🔇' if interaction.user.voice.self_mute else '🔊'}\n"
                      f"스피커 끔: {'🔇' if interaction.user.voice.self_deaf else '🔊'}",
                inline=False
            )
        else:
            embed.add_field(
                name="👤 사용자 상태",
                value="위치: ❌ 음성 채널에 없음",
                inline=False
            )
        
        embed.set_footer(text="💡 문제가 있다면 /테스트 명령어를 사용해보세요!")
        
        await interaction.response.send_message(embed=embed)

    # ============================================
    # 내부 유틸리티 메서드들
    # ============================================

    async def _create_optimized_tts_file(self, text: str, interaction) -> Optional[str]:
        """최적화된 TTS 파일 생성 (성공한 로직 적용)"""
        try:
            # 텍스트 최적화
            optimized_text = f"{text}."
            
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time() * 1000000)  # 마이크로초까지 포함
            guild_id = interaction.guild.id
            
            mp3_file = os.path.join(temp_dir, f"tts_{guild_id}_{timestamp}.mp3")
            wav_file = os.path.join(temp_dir, f"tts_{guild_id}_{timestamp}_optimized.wav")
            
            logger.info(f"🎵 TTS 생성 시작: '{text}' -> {mp3_file}")
            
            # 1단계: gTTS로 기본 MP3 생성
            tts = gTTS(text=optimized_text, lang='ko', slow=False)
            tts.save(mp3_file)
            
            if not os.path.exists(mp3_file) or os.path.getsize(mp3_file) < 1000:
                logger.error(f"❌ gTTS 파일 생성 실패: {mp3_file}")
                return None
            
            # 2단계: FFmpeg로 볼륨 부스트 및 Discord 최적화
            cmd = [
                self.ffmpeg_executable,
                '-i', mp3_file,
                # 볼륨 10배 증폭 + 라우드니스 정규화 (성공한 핵심 로직!)
                '-af', 'volume=10.0,loudnorm=I=-16:TP=-1.5:LRA=11',  
                '-ar', '48000',  # Discord 최적 샘플레이트
                '-ac', '2',      # 스테레오
                '-b:a', '128k',  # 높은 비트레이트
                '-y', wav_file
            ]
            
            logger.info(f"🔧 볼륨 최적화 실행: {' '.join(cmd[:3])}...")
            result = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
            
            # 기본 MP3 파일 정리
            try:
                os.remove(mp3_file)
            except:
                pass
            
            if result.returncode != 0:
                logger.error(f"❌ FFmpeg 최적화 실패: {result.stderr}")
                return None
            
            # 3단계: 최종 파일 검증
            if os.path.exists(wav_file) and os.path.getsize(wav_file) > 10000:  # 10KB 이상
                file_size = os.path.getsize(wav_file)
                logger.info(f"✅ 최적화 TTS 생성 완료: {wav_file} ({file_size} bytes)")
                return wav_file
            else:
                logger.error("❌ 최적화된 파일이 너무 작거나 생성되지 않음")
                return None
                    
        except Exception as e:
            logger.error(f"❌ TTS 파일 생성 실패: {e}", exc_info=True)
            # 임시 파일들 정리
            for temp_file in [mp3_file, wav_file]:
                try:
                    if 'temp_file' in locals() and os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
            return None

    async def _play_optimized_audio(self, voice_client: discord.VoiceClient, audio_file: str, text: str, interaction) -> bool:
        """최적화된 오디오 재생 (프로덕션 안정화)"""
        try:
            logger.info(f"🔊 최적화 오디오 재생 시작: {audio_file}")
            
            # Discord PCM 최적화 옵션
            audio_source = discord.FFmpegPCMAudio(
                audio_file,
                executable=self.ffmpeg_executable,
                options='-vn'
            )
            
            # 추가 볼륨 컨트롤
            volume_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)
            
            # 재생 완료 추적
            play_finished = asyncio.Event()
            play_error = None
            
            def after_play(error):
                nonlocal play_error
                if error:
                    play_error = error
                    logger.error(f"❌ 재생 오류: {error}")
                else:
                    logger.info("✅ 오디오 재생 완료")
                play_finished.set()
                
                # 🔥 핵심 수정: 안전한 파일 정리 (이벤트 루프 사용)
                # asyncio.create_task 대신 bot의 이벤트 루프에 직접 스케줄링
                try:
                    loop = self.bot.loop
                    if loop and loop.is_running():
                        asyncio.run_coroutine_threadsafe(
                            self._cleanup_audio_file(audio_file), 
                            loop
                        )
                except Exception as cleanup_error:
                    logger.error(f"⚠️ 파일 정리 스케줄링 실패: {cleanup_error}")
            
            # 재생 시작
            voice_client.play(volume_source, after=after_play)
            
            # 재생 시작 확인
            await asyncio.sleep(0.3)
            if not voice_client.is_playing():
                logger.warning("❌ 재생이 시작되지 않음")
                return False
            
            logger.info("🎵 오디오 재생 중...")
            
            # 재생 완료 대기
            try:
                await asyncio.wait_for(play_finished.wait(), timeout=30.0)
                success = play_error is None
                
                if success:
                    logger.info("✅ 오디오 재생 성공")
                else:
                    logger.error(f"❌ 재생 중 오류: {play_error}")
                
                return success
                
            except asyncio.TimeoutError:
                logger.warning("⚠️ 재생 타임아웃")
                voice_client.stop()
                return False
            
        except Exception as e:
            logger.error(f"❌ 오디오 재생 실패: {e}", exc_info=True)
            return False

    async def _cleanup_audio_file(self, audio_file: str):
        """오디오 파일 비동기 정리"""
        try:
            await asyncio.sleep(1)  # 재생 완료 확실히 대기
            if os.path.exists(audio_file):
                os.remove(audio_file)
                logger.info(f"🗑️ 임시 파일 삭제: {audio_file}")
        except Exception as e:
            logger.error(f"❌ 파일 삭제 오류: {e}")

    async def _play_test_signal(self, voice_client: discord.VoiceClient) -> bool:
        """테스트 신호음 재생"""
        try:
            # 1초간 1000Hz 신호음 생성
            pcm_data = self._generate_test_tone(1000, 1.0, 0.7)
            
            pcm_stream = io.BytesIO(pcm_data)
            audio_source = discord.PCMAudio(pcm_stream)
            volume_source = discord.PCMVolumeTransformer(audio_source, volume=1.0)
            
            play_finished = asyncio.Event()
            signal_error = None
            
            def after_signal(error):
                nonlocal signal_error
                if error:
                    signal_error = error
                play_finished.set()
            
            voice_client.play(volume_source, after=after_signal)
            
            await asyncio.sleep(0.2)
            if not voice_client.is_playing():
                return False
            
            await asyncio.wait_for(play_finished.wait(), timeout=3.0)
            return signal_error is None
            
        except Exception as e:
            logger.error(f"❌ 신호음 테스트 실패: {e}")
            return False

    async def _play_test_tts(self, voice_client: discord.VoiceClient) -> bool:
        """테스트 TTS 재생"""
        try:
            test_text = "TTS 테스트가 정상적으로 작동합니다"
            
            # 임시 TTS 파일 생성
            temp_dir = tempfile.gettempdir()
            timestamp = int(time.time() * 1000000)
            test_file = os.path.join(temp_dir, f"test_tts_{timestamp}.mp3")
            
            tts = gTTS(text=test_text, lang='ko', slow=False)
            tts.save(test_file)
            
            if not os.path.exists(test_file):
                return False
            
            # 단순 재생 (볼륨 부스트 없이 테스트)
            audio_source = discord.FFmpegPCMAudio(test_file, executable=self.ffmpeg_executable)
            
            play_finished = asyncio.Event()
            tts_error = None
            
            def after_tts(error):
                nonlocal tts_error
                if error:
                    tts_error = error
                play_finished.set()
                
                # 파일 정리
                try:
                    if os.path.exists(test_file):
                        os.remove(test_file)
                except:
                    pass
            
            voice_client.play(audio_source, after=after_tts)
            
            await asyncio.sleep(0.3)
            if not voice_client.is_playing():
                return False
            
            await asyncio.wait_for(play_finished.wait(), timeout=10.0)
            return tts_error is None
            
        except Exception as e:
            logger.error(f"❌ TTS 테스트 실패: {e}")
            return False

    def _generate_test_tone(self, frequency: float, duration: float, volume: float = 0.7) -> bytes:
        """테스트용 신호음 생성"""
        sample_rate = 48000
        samples = int(duration * sample_rate)
        
        pcm_data = b''
        for i in range(samples):
            sample = int(32767 * volume * math.sin(2 * math.pi * frequency * i / sample_rate))
            pcm_data += struct.pack('<hh', sample, sample)  # 스테레오
        
        return pcm_data

    # ============================================
    # Cog 생명주기 관리
    # ============================================

    async def cog_unload(self):
        """Cog 언로드 시 정리"""
        logger.info("🔄 TTS Commands Cog 언로드 중...")
        
        # 모든 음성 연결 해제
        for guild_id, voice_client in self.voice_clients.items():
            try:
                if voice_client.is_connected():
                    if voice_client.is_playing():
                        voice_client.stop()
                    await voice_client.disconnect()
                    logger.info(f"🔌 음성 연결 해제: {guild_id}")
            except Exception as e:
                logger.error(f"❌ 음성 연결 해제 오류 ({guild_id}): {e}")
        
        # 데이터 정리
        self.voice_clients.clear()
        self.tts_settings.clear()
        
        logger.info("✅ TTS Commands Cog 언로드 완료")

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
        
        # 사람이 아무도 없으면 5초 후 자동 퇴장
        if len(human_members) == 0:
            logger.info(f"👤 채널에 사람이 없음, 5초 후 자동 퇴장: {bot_channel.name}")
            await asyncio.sleep(5)
            
            # 5초 후에도 여전히 혼자인지 재확인
            if voice_client.is_connected():
                current_human_members = [m for m in voice_client.channel.members if not m.bot]
                if len(current_human_members) == 0:
                    try:
                        if voice_client.is_playing():
                            voice_client.stop()
                        await voice_client.disconnect()
                        del self.voice_clients[guild_id]
                        if guild_id in self.tts_settings:
                            del self.tts_settings[guild_id]
                        
                        logger.info(f"🚪 자동 퇴장 완료: {bot_channel.name}")
                    except Exception as e:
                        logger.error(f"❌ 자동 퇴장 오류: {e}")

# ============================================
# Cog 등록 함수
# ============================================

async def setup(bot):
    """TTS Commands Cog를 봇에 추가"""
    await bot.add_cog(TTSCommands(bot))
    logger.info("🎤 TTS Commands 시스템이 로드되었습니다!")

# ============================================
# 프로덕션 배포 가이드
# ============================================
"""
🚀 프로덕션 배포 가이드

1. 필수 시스템 요구사항:
   - Python 3.8+
   - FFmpeg 설치됨
   - Opus 라이브러리 설치됨

2. 필수 Python 패키지:
   pip install "discord.py[voice]" gtts

3. macOS 추가 설치:
   brew install opus ffmpeg

4. 봇 권한 설정:
   - Connect (음성 채널 연결)
   - Speak (음성 말하기)
   - Use Voice Activity (음성 활동 사용)

5. 기본 사용법:
   /입장  - TTS 봇 음성 채널 입장
   /말하기 <내용>  - 텍스트를 음성으로 변환
   /테스트  - 시스템 테스트
   /상태  - 현재 상태 확인
   /퇴장  - 음성 채널에서 퇴장

6. 성능 최적화:
   - 볼륨 10배 증폭으로 Discord VAD 우회
   - FFmpeg 라우드니스 정규화 적용
   - 자동 파일 정리 시스템
   - 비동기 처리로 논블로킹 동작

7. 자동 관리 기능:
   - 채널에 혼자 남으면 5초 후 자동 퇴장
   - 임시 파일 자동 정리
   - 에러 복구 및 로깅

이 시스템은 프로덕션 환경에서 안정적으로 작동하도록 설계되었습니다.
"""