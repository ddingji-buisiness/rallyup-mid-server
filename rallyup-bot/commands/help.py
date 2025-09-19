from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands

class HelpCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="RallyUp 봇 사용법을 확인합니다")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 RallyUp Bot 명령어 가이드",
            color=0x0099ff
        )
        
        # 유저 전용 명령어
        embed.add_field(
            name="📝 **유저 전용 명령어**",
            value="```\n"
                  "/유저신청 [유입경로] [배틀태그] [메인포지션] [전시즌티어] [현시즌티어] [최고티어]\n"
                  "- 서버 가입 신청을 위한 정보 등록\n\n"
                  "/대나무숲 [메시지]\n"
                  "- 익명으로 메시지를 전송합니다\n"
                  "```",
            inline=False
        )
        
        # 내전 관련 명령어
        embed.add_field(
            name="🎮 **내전 관련 명령어**",
            value="```\n"
                  "/내전시작 [음성채널명] [세션이름]\n"
                  "- 내전 세션을 시작합니다\n\n"
                  "/내전결과 [A팀 음성채널] [B팀 음성채널] [승리팀]\n"
                  "- 내전 결과를 기록합니다\n\n"
                  "/내전포지션 [A팀 음성채널] [A팀 포지션] [B팀 음성채널] [B팀 포지션]\n"
                  "- 팀 포지션 구성을 설정합니다\n\n"
                  "/내전세션현황\n"
                  "- 현재 진행중인 내전 현황을 확인합니다\n\n"
                  "/내전종료\n"-
                  "- 진행중인 내전 세션을 종료합니다\n"
                  "```",
            inline=False
        )
        
        # 클랜전/스크림 명령어
        # embed.add_field(
        #     name="⚔️ **클랜전/스크림 명령어**",
        #     value="```\n"
        #           "/클랜등록 [클랜명] - 새로운 클랜을 등록합니다\n"
        #           "/클랜목록 - 등록된 클랜 목록을 확인합니다\n"
        #           "/클랜전시작 [A클랜] [B클랜] [A음성채널] [B음성채널]\n"
        #           "/클랜전결과 [A음성채널] [B음성채널] [승리팀] [맵이름]\n"
        #           "/클랜전포지션 [음성채널] [탱커] [딜러1] [딜러2] [힐러1] [힐러2]\n"
        #           "/클랜전조합 [음성채널] [탱커영웅] [딜러1영웅] [딜러2영웅] [힐러1영웅] [힐러2영웅]\n"
        #           "/클랜전종료 - 진행중인 클랜전을 종료합니다\n"
        #           "/클랜전현황 - 현재 클랜전 현황을 확인합니다\n"
        #           "```",
        #     inline=False
        # )
        embed.timestamp = discord.utils.utcnow()
        
        embed.set_footer(
            text="💡 관리자 명령어를 보려면 '/help admin' 을 입력하세요! | RallyUp Bot v2.0",
            icon_url=interaction.client.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="help-admin", description="관리자 전용 명령어를 확인합니다 (관리자만 사용 가능)")
    async def help_admin_command(self, interaction: discord.Interaction):
        # 관리자 권한 체크 (필요시 여기에 권한 체크 로직 추가)
        # if not self.bot.db_manager.is_admin(str(interaction.user.id)):
        #     await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
        #     return
        
        embed = discord.Embed(
            title="🔒 관리자 전용 명령어",
            description="서버 관리자만 사용할 수 있는 명령어들입니다",
            color=0xff6b6b
        )
        
        # 서버 관리
        embed.add_field(
            name="🔧 **서버 관리**",
            value="```\n"
                  "/관리자추가 [유저] - 봇 관리자 권한 부여\n"
                  "/관리자제거 [유저] - 봇 관리자 권한 제거\n"
                  "/관리자목록 - 현재 관리자 목록 확인\n"
                  "```",
            inline=False
        )
        
        # 역할 설정
        embed.add_field(
            name="⚙️ **역할 설정**",
            value="```\n"
                  "/설정역할 [신입역할] [구성원역할] [자동변경] - 자동 역할 할당 설정\n"
                  "/설정확인 - 현재 설정 상태 확인\n"
                  "/역할테스트 [테스트유저] - 역할 설정 테스트\n"
                  "```",
            inline=False
        )
        
        # 신규 유저 관리
        embed.add_field(
            name="👥 **신규 유저 관리**",
            value="```\n"
                  "/신규역할설정 [신규역할] [자동배정활성화] - 신규 입장자 역할 설정\n"
                  "/신규역할현황 - 신규 역할 설정 현황 확인\n"
                  "/신규역할해제 - 신규 역할 설정 해제\n"
                  "```",
            inline=False
        )
        
        # 가입 승인 관리
        embed.add_field(
            name="✅ **가입 승인 관리**",
            value="```\n"
                  "/신청승인 [유저명] [관리자메모] - 가입 신청 승인\n"
                  "/신청거절 [유저명] [관리자메모] - 가입 신청 거절\n"
                  "/유저삭제 [유저명] [삭제사유] - 유저 삭제\n"
                  "/등록유저목록 - 등록된 유저 목록 확인\n"
                  "```",
            inline=False
        )
        
        # 대나무숲 관리
        embed.add_field(
            name="🌿 **대나무숲 관리**",
            value="```\n"
                  "/대나무숲설정 [채널] - 대나무숲 채널 설정\n"
                  "/대나무숲강제공개 [메시지링크] - 특정 메시지 강제 공개\n"
                  "/대나무숲조회 - 대나무숲 현황 조회\n"
                  "/대나무숲통계 - 대나무숲 사용 통계\n"
                  "/대나무숲정보 - 대나무숲 봇 정보\n"
                  "/대나무숲해제 - 대나무숲 채널 설정 해제\n"
                  "```",
            inline=False
        )
        
        # 내전 공지 관리
        embed.add_field(
            name="📢 **내전 공지 관리**",
            value="```\n"
                  "/내전공지채널설정 [채널] - 내전 공지 채널 설정\n"
                  "/내전공지등록 [채널(옵션)] - 내전 모집 공지 등록\n"
                  "/내전모집현황 - 현재 모집중인 내전 현황\n"
                  "/내전모집취소 [모집ID] - 내전 모집 취소\n"
                  "/내전모집통계 - 내전 모집 통계 확인\n"
                  "/내전모집요약 - 내전 모집 요약 정보\n"
                  "```",
            inline=False
        )

        # 스크림 관리
        embed.add_field(
            name="🎯 **스크림 관리**",
            value="```\n"
                "/스크림공지등록 [채널(옵션)] - 스크림 모집 공지 등록\n"
                "/스크림모집현황 - 현재 모집중인 스크림 현황\n"
                "/스크림모집취소 [모집ID] - 스크림 모집 취소\n"
                "```",
            inline=False
        )

        embed.add_field(
            name="📊 **내전 결과 기록**",
            value="`/내전결과시작` - 마감된 내전의 결과 기록 시작\n"
                "`/팀세팅 [경기번호]` - 경기별 팀 구성 설정\n"
                "`/경기기록 [경기번호]` - 경기 결과 및 포지션 기록\n"
                "`/내전현황` - 현재 기록 진행 상황 확인\n"
                "`/내전결과완료` - 모든 기록 완료 및 통계 반영",
            inline=False
        )

        embed.add_field(
            name="👤 개인 정보 & 통계",
            value="`/정보수정 [현시즌티어]` - 개인 정보 업데이트\n"
                "`/내정보` - 내 종합 통계 확인\n"
                "`/유저조회 [@유저]` - 다른 유저 정보 조회\n"
                "`/순위표` - 서버 내 랭킹 확인",
            inline=False
        )

        embed.add_field(
            name="💡 사용 팁",
            value="• 내전 모집 → 마감 후 결과 기록 → 자동 통계 업데이트\n"
                "• 개인 티어는 `/정보수정`으로 언제든 업데이트 가능\n"
                "• 포지션별 세부 통계가 자동으로 수집됩니다\n"
                "• 같은 내전에 추가 경기 기록 시 경기번호 확인 필수",
            inline=False
        )
        
        embed.set_footer(
            text="⚠️ 관리자 명령어는 신중하게 사용해주세요! | RallyUp Bot v2.0"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCommand(bot))