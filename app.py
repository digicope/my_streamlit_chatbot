"""Streamlit 웹 챗봇 메인 엔트리 포인트"""
import os
import streamlit as st
# from dotenv import load_dotenv

from src.llm import LLMClient
from src.prompts import DEFAULT_SYSTEM_PROMPT, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from src.ui import render_sidebar, render_chat_messages, render_streaming_response
from src.utils import format_error_message, validate_api_key, logger

# 환경변수 로드
# load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Streamlit Web Chatbot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

if "model" not in st.session_state:
    st.session_state.model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

if "temperature" not in st.session_state:
    st.session_state.temperature = DEFAULT_TEMPERATURE

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

# API 키 검증
api_key = os.getenv("OPENAI_API_KEY")
is_valid, error_msg = validate_api_key(api_key)

if not is_valid:
    st.error(f"⚠️ {error_msg}")
    st.info("💡 .env 파일에 OPENAI_API_KEY를 설정하거나 환경변수로 지정해주세요.")
    st.stop()

# LLM 클라이언트 초기화
try:
    llm_client = LLMClient(api_key=api_key)
except ValueError as e:
    st.error(f"⚠️ {str(e)}")
    st.stop()

# 메인 UI
st.title("💬 Streamlit Web Chatbot")
st.caption("OpenAI API를 사용하는 대화형 챗봇")

# 사이드바 렌더링
model, temperature, system_prompt, should_reset = render_sidebar(
    default_model=st.session_state.model,
    default_temperature=st.session_state.temperature,
    default_system_prompt=st.session_state.system_prompt
)

# 세션 상태 업데이트
st.session_state.model = model
st.session_state.temperature = temperature
st.session_state.system_prompt = system_prompt

# 채팅 메시지 히스토리 렌더링
render_chat_messages(st.session_state.messages)

# 사용자 입력 처리
if user_input := st.chat_input("메시지를 입력하세요..."):
    # 사용자 메시지 추가 및 표시
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    
    # 어시스턴트 응답 생성
    with st.chat_message("assistant"):
        # 로딩 인디케이터
        with st.spinner("답변을 생성하는 중..."):
            try:
                # OpenAI API 포맷으로 메시지 변환
                api_messages = []
                
                # 시스템 프롬프트 추가
                if st.session_state.system_prompt:
                    api_messages.append({
                        "role": "system",
                        "content": st.session_state.system_prompt
                    })
                
                # 대화 히스토리 추가 (시스템 프롬프트 제외)
                for msg in st.session_state.messages:
                    api_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
                
                # 스트리밍 응답 생성
                response_placeholder = st.empty()
                stream_generator = llm_client.stream_chat(
                    messages=api_messages,
                    model=st.session_state.model,
                    temperature=st.session_state.temperature
                )
                
                # 스트리밍 응답 렌더링
                full_response = render_streaming_response(
                    response_placeholder,
                    stream_generator
                )
                
                # 어시스턴트 메시지를 세션 상태에 추가
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response
                })
                
            except ValueError as e:
                error_message = str(e)
                st.error(f"❌ {error_message}")
                logger.error(f"Error in chat: {error_message}")
            except Exception as e:
                error_message = format_error_message(e)
                st.error(f"❌ {error_message}")
                logger.error(f"Unexpected error: {e}", exc_info=True)

# 사이드바 하단에 정보 표시
with st.sidebar:
    st.divider()
    st.caption(f"모델: {model}")
    st.caption(f"Temperature: {temperature}")
    st.caption(f"대화 수: {len(st.session_state.messages)}")
