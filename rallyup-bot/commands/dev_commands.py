import os
import random
import discord
from discord.ext import commands
from discord import app_commands
from typing import Literal
import asyncio

class DevCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.developer_ids = [
            "386917108455309316",
            "415524200720105482",
        ]

        try:
            dev_ids_env = os.getenv('DEVELOPER_IDS', '')
            if dev_ids_env:
                env_ids = [id.strip() for id in dev_ids_env.split(',') if id.strip()]
                # 중복 제거하면서 합치기
                all_ids = list(set(self.developer_ids + env_ids))
                self.developer_ids = all_ids
                print(f"🔍 [개발] 환경변수에서 추가 로드: {env_ids}")
        except Exception as e:
            print(f"❌ [개발] 환경변수 로드 실패: {e}")
        
        print(f"🔍 [개발] 최종 등록된 개발자 ID: {self.developer_ids}")
    
    def is_developer(self, user_id) -> bool:
        user_id_str = str(user_id)
        result = user_id_str in self.developer_ids
        print(f"🔍 [권한체크] 사용자 ID: {user_id_str}, 결과: {result}")
        return result

    @app_commands.command(name="dev-등록", description="[개발용] 현재 사용자를 개발자로 등록합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_register(self, interaction):
        # 기존 개발자만 새로운 개발자 등록 가능
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                f"❌ 권한이 없습니다.\n"
                f"**현재 사용자 ID:** `{interaction.user.id}`\n"
                f"기존 개발자에게 이 ID를 전달하여 등록을 요청하세요.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"✅ 이미 개발자로 등록되어 있습니다.\n"
            f"**등록된 개발자 수:** {len(self.developer_ids)}명",
            ephemeral=True
        )

    @app_commands.command(name="dev-추가", description="[개발용] 새로운 개발자를 추가합니다")
    @app_commands.describe(사용자="추가할 사용자")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_add_user(self, interaction, 사용자: discord.Member):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 기존 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        new_user_id = str(사용자.id)
        
        if new_user_id in self.developer_ids:
            await interaction.response.send_message(
                f"ℹ️ {사용자.display_name}님은 이미 개발자로 등록되어 있습니다.",
                ephemeral=True
            )
            return
        
        # 메모리에서 추가 (재시작 시까지 유효)
        self.developer_ids.append(new_user_id)
        
        await interaction.response.send_message(
            f"✅ {사용자.display_name}님을 개발자로 추가했습니다!\n"
            f"**사용자 ID:** `{new_user_id}`\n"
            f"**등록된 개발자 수:** {len(self.developer_ids)}명\n\n"
            f"⚠️ **주의:** 봇 재시작 시 초기화됩니다.\n"
            f"영구 등록을 위해서는 `.env` 파일의 `DEVELOPER_IDS`에 추가하세요.",
            ephemeral=True
        )

    @app_commands.command(name="dev-내전시작", description="[개발용] 가상 내전 세션을 시작합니다")
    @app_commands.describe(
        participant_count="참가자 수 (기본: 10명)",
        session_name="세션 이름 (선택사항)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def dev_start_scrim(
        self, 
        interaction,
        participant_count: int = 10,
        session_name: str = None
    ):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        if participant_count < 4 or participant_count > 20:
            await interaction.response.send_message(
                "❌ 참가자 수는 4-20명 사이여야 합니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🧪 가상 내전 세션을 시작 중입니다...", ephemeral=True
        )
        
        try:
            # 기존 활성 세션 확인
            existing_session = await self.bot.db_manager.get_active_session(str(interaction.guild_id))
            if existing_session:
                await interaction.followup.send(
                    "❌ 이미 진행 중인 내전 세션이 있습니다.\n"
                    f"먼저 `/dev-내전종료`를 실행해주세요.",
                    ephemeral=True
                )
                return
            
            # 🔥 가상 참가자 생성 (랜덤 이름)
            fake_names = [
                "김민준", "이서현", "박지호", "최유진", "정도윤",
                "강서연", "조민서", "윤지우", "장예준", "임지민",
                "한지원", "오수빈", "신예원", "문준혁", "배시우",
                "송지율", "노시온", "고은우", "권서진", "남주안"
            ]
            
            # 랜덤하게 이름 선택
            selected_names = random.sample(fake_names, participant_count)
            
            fake_members = []
            for i, name in enumerate(selected_names):
                fake_member = type('FakeMember', (), {
                    'id': f"fake_user_{i+1}_{interaction.user.id}_{random.randint(1000, 9999)}",
                    'display_name': name,
                    'bot': False
                })()
                fake_members.append(fake_member)
            
            print(f"🔍 [개발] 가상 참가자 {participant_count}명 생성 완료")
            
            # 세션 생성
            session_uuid = await self.bot.db_manager.create_scrim_session(
                guild_id=str(interaction.guild_id),
                voice_channel="개발-내전방",
                participants=fake_members,
                started_by=str(interaction.user.id),
                session_name=session_name or f"테스트세션_{random.randint(100, 999)}"
            )
            
            # 성공 메시지
            embed = discord.Embed(
                title="🧪 [개발용] 가상 내전 세션 시작!",
                description=f"**개발-내전방**에서 테스트 세션이 시작되었습니다!",
                color=0xff9500
            )
            
            # 참여자 목록 (2열로 표시)
            participants_list = []
            for i, participant in enumerate(fake_members):
                participants_list.append(f"{i+1}. {participant.display_name}")
            
            # 참여자를 두 그룹으로 나누기
            mid_point = len(participants_list) // 2 + (len(participants_list) % 2)
            left_column = participants_list[:mid_point]
            right_column = participants_list[mid_point:]
            
            embed.add_field(
                name=f"👥 가상 참여자 ({len(fake_members)}명)",
                value="\n".join(left_column),
                inline=True
            )
            
            if right_column:
                embed.add_field(
                    name="​", # 공백 문자
                    value="\n".join(right_column),
                    inline=True
                )
            
            # 세션 정보
            session_info = f"**세션 ID**: `{session_uuid[:8]}...`\n"
            session_info += f"**세션명**: {session_name or f'테스트세션_{random.randint(100, 999)}'}\n"
            session_info += f"**운영자**: {interaction.user.display_name} (개발자)"
            
            embed.add_field(
                name="📋 세션 정보",
                value=session_info,
                inline=False
            )
            
            # 테스트 명령어 안내
            embed.add_field(
                name="🔧 테스트 명령어",
                value="• `/dev-내전결과` - 랜덤 팀으로 경기 결과 생성\n"
                      "• `/dev-세션현황` - 현재 세션 상태 확인\n"
                      "• `/dev-내전종료` - 세션 종료 및 요약",
                inline=False
            )
            
            embed.set_footer(text="모든 참가자 데이터가 자동으로 추적됩니다!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ [개발] 세션 시작 오류: {str(e)}")
            import traceback
            print(f"❌ [개발] 스택 트레이스: {traceback.format_exc()}")
            
            await interaction.followup.send(
                f"❌ 세션 시작 중 오류: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="dev-세션현황", description="[개발용] 현재 테스트 세션 상태를 확인합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_session_status(self, interaction):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message("🔍 세션 현황을 확인 중입니다...", ephemeral=True)
        
        try:
            session_info = await self.bot.db_manager.get_active_session_details(str(interaction.guild_id))
            
            if not session_info:
                await interaction.followup.send(
                    "❌ 현재 진행 중인 테스트 세션이 없습니다.\n"
                    "`/dev-내전시작` 명령어로 세션을 시작해주세요.",
                    ephemeral=True
                )
                return
            
            session, participants, matches = session_info
            
            embed = discord.Embed(
                title="🧪 [개발용] 테스트 세션 현황",
                description=f"**{session['voice_channel']}** 세션 상태",
                color=0xff9500
            )
            
            # 세션 기본 정보
            from datetime import datetime
            started_time = datetime.fromisoformat(session['started_at'])
            duration = datetime.now() - started_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            embed.add_field(
                name="⏱️ 세션 정보",
                value=f"**세션명**: {session.get('session_name', '테스트세션')}\n"
                      f"**진행 시간**: {hours}시간 {minutes}분\n"
                      f"**완료된 경기**: {len(matches)}경기\n"
                      f"**가상 참여자**: {len(participants)}명",
                inline=True
            )
            
            # 가상 참여자들 (일부만 표시)
            participants_display = []
            for p in participants[:8]:  # 최대 8명까지만 표시
                participants_display.append(f"🤖 {p['username']}")
            
            if len(participants) > 8:
                participants_display.append(f"... 외 {len(participants) - 8}명")
            
            embed.add_field(
                name="👥 가상 참여자",
                value="\n".join(participants_display),
                inline=True
            )
            
            # 최근 경기 결과
            if matches:
                recent_matches = []
                for match in matches[-3:]:  # 최근 3경기
                    winner = "A팀" if match['winning_team'] == 1 else "B팀"
                    match_time = datetime.fromisoformat(match['created_at'])
                    recent_matches.append(f"**{match['match_number']}경기**: {winner} 승리 (<t:{int(match_time.timestamp())}:R>)")
                
                embed.add_field(
                    name="🏆 최근 경기 결과",
                    value="\n".join(recent_matches),
                    inline=False
                )
            
            # 세션 통계
            if matches:
                team1_wins = sum(1 for m in matches if m['winning_team'] == 1)
                team2_wins = len(matches) - team1_wins
                avg_time = duration.total_seconds() / len(matches) / 60 if len(matches) > 0 else 0
                
                embed.add_field(
                    name="📈 세션 통계",
                    value=f"**A팀 승**: {team1_wins}경기\n**B팀 승**: {team2_wins}경기\n**경기당 평균**: {avg_time:.1f}분",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📈 세션 통계",
                    value="아직 경기가 없습니다.\n`/dev-내전결과`로 경기를 생성해보세요!",
                    inline=True
                )
            
            embed.set_footer(text=f"세션 ID: {session['session_uuid'][:8]}... | 개발 테스트 환경")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 세션 현황 조회 중 오류: {str(e)}", ephemeral=True)

    @app_commands.command(name="dev-내전종료", description="[개발용] 현재 테스트 세션을 종료합니다")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_end_scrim(self, interaction):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message("🔍 세션 종료 중입니다...", ephemeral=True)
        
        try:
            session_info = await self.bot.db_manager.get_active_session_details(str(interaction.guild_id))
            
            if not session_info:
                await interaction.followup.send(
                    "❌ 현재 진행 중인 테스트 세션이 없습니다.",
                    ephemeral=True
                )
                return
            
            session, participants, matches = session_info
            
            # 세션 종료
            await self.bot.db_manager.end_scrim_session(session['id'])
            
            # 세션 요약 생성
            embed = discord.Embed(
                title="🧪 [개발용] 테스트 세션 종료!",
                description=f"**{session['voice_channel']}** 세션이 완료되었습니다",
                color=0xff6b6b
            )
            
            # 세션 요약
            from datetime import datetime
            started_time = datetime.fromisoformat(session['started_at'])
            duration = datetime.now() - started_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            
            embed.add_field(
                name="📊 세션 요약",
                value=f"**세션명**: {session.get('session_name', '테스트세션')}\n"
                      f"**총 진행 시간**: {hours}시간 {minutes}분\n"
                      f"**총 경기 수**: {len(matches)}경기\n"
                      f"**가상 참여자**: {len(participants)}명",
                inline=True
            )
            
            # 경기 결과 요약
            if matches:
                team1_wins = sum(1 for m in matches if m['winning_team'] == 1)
                team2_wins = len(matches) - team1_wins
                avg_time = duration.total_seconds() / len(matches) / 60
                
                embed.add_field(
                    name="🏆 경기 결과",
                    value=f"**A팀**: {team1_wins}승\n**B팀**: {team2_wins}승\n**경기당 평균**: {avg_time:.1f}분",
                    inline=True
                )
            
            # 생성된 데이터 요약
            embed.add_field(
                name="📈 생성된 테스트 데이터",
                value=f"✅ {len(matches)}개의 경기 데이터\n"
                      f"✅ {len(participants)}명의 사용자 통계\n"
                      f"✅ 팀메이트/라이벌 관계 데이터\n"
                      f"✅ 세션 참여 패턴 데이터",
                inline=False
            )
            
            embed.set_footer(text="모든 테스트 데이터가 개인 통계에 반영되었습니다!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 세션 종료 중 오류: {str(e)}", ephemeral=True)

    @app_commands.command(name="dev-내전결과", description="[개발용] 가상 내전 결과 생성 (랜덤 팀 배정)")
    @app_commands.describe(
        winning_team="승리팀 (1 또는 2, 기본값: 랜덤)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def dev_match_result(
        self, 
        interaction,
        winning_team: Literal[1, 2] = None
    ):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🧪 가상 내전 결과를 생성 중입니다...", ephemeral=True
        )
        
        try:
            # 현재 활성 세션 확인
            session_info = await self.bot.db_manager.get_active_session_details(str(interaction.guild_id))
            
            if not session_info:
                await interaction.followup.send(
                    "❌ 진행 중인 세션이 없습니다.\n"
                    "먼저 `/dev-내전시작`을 실행해주세요.",
                    ephemeral=True
                )
                return
            
            session, participants, matches = session_info
            
            if len(participants) < 10:
                await interaction.followup.send(
                    f"❌ 10명이 필요합니다. (현재: {len(participants)}명)\n"
                    "더 많은 참가자로 세션을 다시 시작해주세요.",
                    ephemeral=True
                )
                return
            
            # 🔥 랜덤 팀 배정 (매번 다르게)
            available_participants = participants.copy()
            random.shuffle(available_participants)  # 매번 섞기
            
            team1_members = []
            team2_members = []
            
            for i, p in enumerate(available_participants[:10]):  # 10명만 선택
                fake_member = type('FakeMember', (), {
                    'id': p['user_id'],
                    'display_name': p['username'],
                    'bot': False
                })()
                
                if i < 5:
                    team1_members.append(fake_member)
                else:
                    team2_members.append(fake_member)
            
            # 승리팀 결정 (랜덤 or 지정)
            if winning_team is None:
                winning_team = random.choice([1, 2])
            
            print(f"🔍 [개발] 랜덤 팀 배정 완료: A팀 5명, B팀 5명, 승리팀={winning_team}")
            
            # DatabaseManager의 create_match 사용
            match_uuid = await self.bot.db_manager.create_match(
                guild_id=str(interaction.guild_id),
                team1_channel="개발-A팀",
                team2_channel="개발-B팀",
                winning_team=winning_team,
                team1_members=team1_members,
                team2_members=team2_members
            )
            
            print(f"🔍 [개발] 매치 생성 완료: {match_uuid}")
            
            # 성공 메시지
            winner_name = "A팀" if winning_team == 1 else "B팀"
            loser_name = "B팀" if winning_team == 1 else "A팀"
            
            embed = discord.Embed(
                title="🧪 [개발용] 가상 내전 결과 생성 완료",
                description=f"**{winner_name}**이 승리했습니다! (랜덤 팀 배정)",
                color=0xff9500
            )
            
            # A팀 멤버
            team1_list = "\n".join([f"{i+1}. {member.display_name}" for i, member in enumerate(team1_members)])
            embed.add_field(
                name=f"🔵 A팀 {'(승리)' if winning_team == 1 else '(패배)'}",
                value=team1_list,
                inline=True
            )
            
            # B팀 멤버
            team2_list = "\n".join([f"{i+1}. {member.display_name}" for i, member in enumerate(team2_members)])
            embed.add_field(
                name=f"🔴 B팀 {'(승리)' if winning_team == 2 else '(패배)'}",
                value=team2_list,
                inline=True
            )
            
            # 업데이트된 통계
            embed.add_field(
                name="📊 업데이트된 데이터",
                value=f"✅ 기본 승패 기록 (total_games, total_wins)\n"
                      f"✅ 승점 변동 (승리팀 +25점, 패배팀 -15점)\n"
                      f"✅ 세션 경기 수: {len(matches) + 1}경기\n"
                      f"✅ 랜덤 팀 조합으로 다양한 데이터 생성",
                inline=False
            )
            
            embed.add_field(
                name="🔧 다음 단계",
                value="`/dev-포지션 탱딜딜힐힐 딜탱딜힐힐`\n포지션 정보를 추가해보세요!",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ [개발] 내전결과 생성 오류: {str(e)}")
            import traceback
            print(f"❌ [개발] 스택 트레이스: {traceback.format_exc()}")
            
            await interaction.followup.send(
                f"❌ 생성 중 오류: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="dev-포지션", description="[개발용] 최근 가상 매치에 포지션 추가")
    @app_commands.describe(
        team_a_positions="A팀 포지션 (예: 탱딜딜힐힐)",
        team_b_positions="B팀 포지션 (예: 딜탱딜힐힐)"
    )
    @app_commands.default_permissions(manage_guild=True)
    async def dev_position(self, interaction, team_a_positions: str, team_b_positions: str):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        # 포지션 검증 (오버워치 탱1딜2힐2)
        for pos_name, pos in [("A팀", team_a_positions), ("B팀", team_b_positions)]:
            if len(pos) != 5 or not all(c in '탱딜힐' for c in pos):
                await interaction.response.send_message(
                    f"❌ {pos_name} 포지션 형식 오류: {pos}\n5글자의 탱/딜/힐 조합이어야 합니다.",
                    ephemeral=True
                )
                return
            
            # 오버워치 구성 체크 (탱1딜2힐2)
            tank_count = pos.count('탱')
            dps_count = pos.count('딜')
            support_count = pos.count('힐')
            
            if tank_count != 1 or dps_count != 2 or support_count != 2:
                await interaction.response.send_message(
                    f"❌ {pos_name} 포지션이 오버워치 구성에 맞지 않습니다: {pos}\n"
                    f"**필요:** 탱1딜2힐2 / **현재:** 탱{tank_count}딜{dps_count}힐{support_count}",
                    ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            "🧪 포지션 정보를 추가 중입니다...", ephemeral=True
        )
        
        try:
            # DatabaseManager 사용
            match_uuid = await self.bot.db_manager.find_recent_match(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                minutes=10
            )
            
            if not match_uuid:
                await interaction.followup.send(
                    "❌ 최근 개발용 매치를 찾을 수 없습니다.\n먼저 `/dev-내전결과`를 실행하세요.",
                    ephemeral=True
                )
                return
            
            # DatabaseManager의 add_position_data 사용
            await self.bot.db_manager.add_position_data(
                match_uuid=match_uuid,
                team1_positions=team_a_positions,
                team2_positions=team_b_positions
            )
            
            # 성공 메시지
            embed = discord.Embed(
                title="✅ [개발용] 포지션 정보 추가 완료",
                description="가상 매치에 포지션 정보가 추가되었습니다!",
                color=0xff9500
            )
            
            embed.add_field(
                name="🔵 A팀 포지션",
                value=f"`{team_a_positions}`",
                inline=True
            )
            
            embed.add_field(
                name="🔴 B팀 포지션", 
                value=f"`{team_b_positions}`",
                inline=True
            )
            
            embed.add_field(
                name="📊 업데이트된 통계",
                value="✅ 포지션별 승률 (tank_games, dps_games, support_games)\n✅ 개인 매치업 데이터 (user_matchups 테이블)\n✅ 포지션 조합 분석 데이터",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ [디버깅] 포지션 추가 오류: {str(e)}")
            import traceback
            print(f"❌ [디버깅] 스택 트레이스: {traceback.format_exc()}")
            
            await interaction.followup.send(
                f"❌ 포지션 추가 중 오류: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="dev-확인", description="[개발용] 데이터베이스 상태 확인")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_check(self, interaction):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message("🔍 데이터베이스 상태를 확인 중입니다...", ephemeral=True)
        
        try:
            import aiosqlite
            
            async with aiosqlite.connect(self.bot.db_manager.db_path, timeout=10.0) as db:
                # 데이터 개수 확인
                counts = {}
                for table in ['matches', 'participants', 'users', 'user_matchups', 'teammate_combinations', 'scrim_sessions', 'session_participants']:
                    async with db.execute(f"SELECT COUNT(*) FROM {table}") as cursor:
                        counts[table] = (await cursor.fetchone())[0]
                
                # 실제 통계 확인
                async with db.execute('''
                    SELECT username, total_games, total_wins, score, total_sessions
                    FROM users 
                    WHERE discord_id LIKE 'fake_user_%'
                    ORDER BY score DESC
                    LIMIT 5
                ''') as cursor:
                    user_stats = await cursor.fetchall()
                
                # 현재 활성 세션
                async with db.execute('''
                    SELECT session_name, total_participants, total_matches, started_at
                    FROM scrim_sessions 
                    WHERE session_status = 'active'
                    ORDER BY started_at DESC
                    LIMIT 1
                ''') as cursor:
                    active_session = await cursor.fetchone()
            
            embed = discord.Embed(
                title="🧪 [개발용] 데이터베이스 상태",
                description="현재 저장된 테스트 데이터 현황",
                color=0xff9500
            )
            
            embed.add_field(
                name="📊 데이터 개수",
                value=f"**매치:** {counts['matches']}개\n"
                      f"**참가자:** {counts['participants']}명\n"
                      f"**사용자:** {counts['users']}명\n"
                      f"**매치업:** {counts['user_matchups']}개\n"
                      f"**팀메이트 조합:** {counts['teammate_combinations']}개\n"
                      f"**세션:** {counts['scrim_sessions']}개",
                inline=True
            )
            
            # 현재 세션 상태
            if active_session:
                from datetime import datetime
                started_time = datetime.fromisoformat(active_session[3])
                duration = datetime.now() - started_time
                hours, remainder = divmod(int(duration.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                
                embed.add_field(
                    name="🎮 활성 세션",
                    value=f"**이름:** {active_session[0]}\n"
                          f"**참여자:** {active_session[1]}명\n"
                          f"**경기 수:** {active_session[2]}경기\n"
                          f"**진행 시간:** {hours}시간 {minutes}분",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🎮 활성 세션",
                    value="현재 진행 중인 세션 없음",
                    inline=True
                )
            
            if user_stats:
                stats_info = []
                for stat in user_stats:
                    username, total_games, total_wins, score, total_sessions = stat
                    winrate = round((total_wins / total_games * 100), 1) if total_games > 0 else 0
                    stats_info.append(f"{username}: {total_games}경기 {winrate}% ({score}점)")
                
                embed.add_field(
                    name="🏆 상위 사용자 (상위 5명)",
                    value="\n".join(stats_info),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 확인 중 오류: {str(e)}", ephemeral=True)

    @app_commands.command(name="dev-정리", description="[개발용] 가상 데이터 정리")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_cleanup(self, interaction):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            "🧹 가상 데이터를 정리 중입니다...", ephemeral=True
        )
        
        try:
            import aiosqlite
            
            async with aiosqlite.connect(
                self.bot.db_manager.db_path, 
                timeout=10.0
            ) as db:
                await db.execute('PRAGMA journal_mode=WAL')
                
                # 🔥 순서대로 삭제 (FK 제약조건 고려)
                await db.execute("DELETE FROM teammate_combinations WHERE user1_id LIKE 'fake_user_%' OR user2_id LIKE 'fake_user_%'")
                await db.execute("DELETE FROM user_matchups WHERE user1_id LIKE 'fake_user_%' OR user2_id LIKE 'fake_user_%'")
                await db.execute("DELETE FROM participants WHERE user_id LIKE 'fake_user_%'")
                await db.execute("DELETE FROM session_participants WHERE user_id LIKE 'fake_user_%'")
                await db.execute("DELETE FROM users WHERE discord_id LIKE 'fake_user_%'")
                await db.execute("DELETE FROM matches WHERE team1_channel = '개발-A팀'")
                await db.execute("DELETE FROM scrim_sessions WHERE voice_channel = '개발-내전방'")
                
                await db.commit()
            
            embed = discord.Embed(
                title="✅ [개발용] 데이터 정리 완료",
                description="모든 가상 테스트 데이터가 삭제되었습니다",
                color=0x00ff88
            )
            
            embed.add_field(
                name="🧹 삭제된 데이터",
                value="✅ 가상 사용자 데이터\n"
                      "✅ 가상 경기 데이터\n"
                      "✅ 팀메이트/매치업 데이터\n"
                      "✅ 세션 데이터\n"
                      "✅ 참가자 데이터",
                inline=False
            )
            
            embed.add_field(
                name="🔄 다음 단계",
                value="`/dev-내전시작`으로 새로운 테스트 세션을 시작하세요!",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 정리 중 오류: {str(e)}", ephemeral=True
            )

    @app_commands.command(name="dev-ping", description="[개발용] 봇 응답 테스트")
    @app_commands.default_permissions(manage_guild=True)
    async def dev_ping(self, interaction):
        if not self.is_developer(interaction.user.id):
            await interaction.response.send_message(
                "❌ 이 명령어는 개발자만 사용할 수 있습니다.", ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            f"🏓 Pong! 봇이 정상 작동 중입니다.\n"
            f"**DB 경로:** {self.bot.db_manager.db_path}\n"
            f"**사용자 ID:** {interaction.user.id}\n"
            f"**서버 ID:** {interaction.guild_id}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(DevCommands(bot))