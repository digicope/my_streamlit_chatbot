import os
from pathlib import Path

import streamlit as st
# from dotenv import load_dotenv
from openai import OpenAI

# ENV_PATH = Path(r"C:\env\.env")
MODEL = "gpt-4o-mini"

# load_dotenv(ENV_PATH)

st.set_page_config(page_title="웹 챗봇", page_icon="💬", layout="centered")
st.title("웹 챗봇")
st.caption(f"모델: {MODEL}")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "error" not in st.session_state:
    st.session_state.error = ""


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error(
            f"`{ENV_PATH}` 파일에서 `OPENAI_API_KEY`를 읽지 못했습니다. "
            "키를 확인한 뒤 다시 실행해 주세요."
        )
        st.stop()
    return OpenAI(api_key=api_key)


def ask_model(history: list[dict[str, str]]) -> str:
    client = get_client()
    response = client.responses.create(
        model=MODEL,
        instructions=(
            "당신은 친절하고 명확하게 답하는 도우미입니다. "
            "사용자가 쓴 언어로 답하고, 불필요하게 길게 설명하지 않습니다."
        ),
        input=[
            {"role": message["role"], "content": message["content"]}
            for message in history
        ],
    )
    return (response.output_text or "").strip() or "빈 응답을 받았습니다."


chat_area = st.container(height=480, border=True)
with chat_area:
    if not st.session_state.messages:
        st.markdown("안녕하세요. 아래에 메시지를 입력하면 대화를 시작합니다.")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if st.session_state.error:
    st.error(st.session_state.error)

with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_input("메시지", placeholder="메시지를 입력하세요")
    submitted = st.form_submit_button("전송", use_container_width=True)

if submitted:
    text = user_text.strip()
    if not text:
        st.session_state.error = "메시지를 입력한 뒤 전송해 주세요."
        st.rerun()

    st.session_state.error = ""
    st.session_state.messages.append({"role": "user", "content": text})
    try:
        with st.spinner("응답을 생성하는 중..."):
            answer = ask_model(st.session_state.messages)
    except Exception as exc:
        st.session_state.messages.pop()
        st.session_state.error = f"OpenAI API 호출에 실패했습니다: {exc}"
        st.rerun()

    st.session_state.messages.append({"role": "assistant", "content": answer})
    st.rerun()
