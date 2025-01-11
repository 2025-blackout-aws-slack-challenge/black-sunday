from fastapi import APIRouter, Form, BackgroundTasks
from src.domain.slackbot.repo import get_recent_messages, send_slack_message
from src.domain.summary.service import generate_summary
from src.domain.synectics.service import generate_synectics
from src.domain.user.service import UserService
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
import os

router = APIRouter(prefix="/slack")
slack_client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))

# ✅ Slack 사용자 이메일 조회 함수
def get_user_email(user_id: str) -> str:
    try:
        response = slack_client.users_info(user=user_id)
        email = response["user"]["profile"]["email"]
        return email
    except SlackApiError as e:
        print(f"❌ 사용자 이메일 조회 실패: {e.response['error']}")
        return None

# ✅ 메시지 분할 전송 함수
def send_long_message(channel_id: str, text: str, chunk_size: int = 3500):
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size]
        try:
            send_slack_message(channel_id, chunk)
        except SlackApiError as e:
            print(f"❌ Slack API 에러: {e.response['error']}")

# ✅ 메시지 포맷 함수
def format_result_message(result: str, result_type: str) -> str:
    emoji = {
        "요약": "📝",
        "발상": "💡"
    }.get(result_type, "💬")

    return f"{emoji} *{result_type} 결과:*\n{result}"

# ✅ Slack Slash Command 핸들러
@router.post("/commands")
async def handle_slack_commands(
    background_tasks: BackgroundTasks,
    command: str = Form(...),
    text: str = Form(...),
    channel_id: str = Form(...),
    user_id: str = Form(...)  # ✅ Slack이 자동으로 제공하는 user_id 사용
):
    args = text.strip().split()

    # ✅ 사용법 안내
    if not args or args[0] not in ["요약하기", "발상하기"]:
        return {
            "response_type": "ephemeral",
            "text": (
                ":robot_face: *아이디어 회의 Slack봇 사용법*\n\n"
                ":memo: *명령어 목록:*\n"
                "`/idea 요약하기` - 최근 대화 내용을 요약합니다.\n"
                "`/idea 발상하기 <단어1> <단어2>` - 두 단어를 기반으로 창의적인 문장을 생성합니다.\n\n"
                ":bulb: *시네틱스(Synectics)란?*\n"
                "> 서로 관련이 없어 보이는 두 개의 개념을 결합하여 창의적이고 혁신적인 아이디어를 도출하는 기법입니다.\n\n"
                ":exclamation: *사용 예시:*\n"
                "`/idea 요약하기`\n"
                "`/idea 발상하기 피자 자전거`\n"
            )
        }

    # ✅ user_id로 이메일 조회
    user_email = get_user_email(user_id)
    if not user_email:
        return {
            "response_type": "ephemeral",
            "text": "❗ 사용자 이메일을 조회할 수 없습니다. 관리자에게 문의하세요."
        }

    command_type = args[0]

    # ✅ "요약하기" 명령어 처리
    if command_type == "요약하기":
        background_tasks.add_task(process_summary, channel_id, user_email)
        return {
            "response_type": "in_channel",
            "text": "📝 최근 대화 내용을 요약 중입니다. 잠시만 기다려주세요!"
        }

    # ✅ "발상하기" 명령어 처리
    elif command_type == "발상하기":
        if len(args) < 3:
            return {
                "response_type": "ephemeral",
                "text": "❗ *발상하기* 명령어 사용법: `/idea 발상하기 <단어1> <단어2>`"
            }
        word_a, word_b = args[1], args[2]
        background_tasks.add_task(process_synectics, word_a, word_b, channel_id)
        return {
            "response_type": "in_channel",
            "text": f"💡 *'{word_a}'*와 *'{word_b}'*를 기반으로 창의적인 문장을 생성 중입니다!"
        }

# ✅ Slack 요약 처리
async def process_summary(channel_id: str, user_email: str):
    try:
        recent_messages = get_recent_messages(channel_id, limit=10)

        # ✅ 이메일 기반으로 topic 조회
        topic = await UserService.get_user_topic(user_email)

        # ✅ 요약 생성
        summary = generate_summary(recent_messages, topic)
        formatted_message = format_result_message(summary, "요약")
        send_long_message(channel_id, formatted_message)

    except Exception as e:
        send_slack_message(channel_id, f"❌ 요약 생성 중 오류 발생: {str(e)}")

# ✅ Slack 시네틱스 처리
def process_synectics(word_a: str, word_b: str, channel_id: str):
    try:
        synectics_result = generate_synectics(word_a, word_b)
        formatted_message = format_result_message(synectics_result, "시네틱스")
        send_long_message(channel_id, formatted_message)
    except Exception as e:
        send_slack_message(channel_id, f"❌ 시네틱스 생성 중 오류 발생: {str(e)}")