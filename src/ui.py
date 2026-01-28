"""채팅 UI 렌더링 함수"""
import streamlit as st
from typing import Optional


def render_sidebar(
    default_model: str,
    default_temperature: float,
    default_system_prompt: str
) -> tuple[str, float, str, bool]:
    """
    사이드바 UI 렌더링
    
    Args:
        default_model: 기본 모델명
        default_temperature: 기본 온도 값
        default_system_prompt: 기본 시스템 프롬프트
        
    Returns:
        (모델명, 온도, 시스템 프롬프트, 초기화 여부)
    """
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # 모델 선택
        model = st.text_input(
            "모델",
            value=st.session_state.get("model", default_model),
            help="사용할 OpenAI 모델을 입력하세요 (예: gpt-4o-mini, gpt-4)"
        )
        
        # Temperature 슬라이더
        temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=st.session_state.get("temperature", default_temperature),
            step=0.1,
            help="값이 높을수록 더 창의적인 응답을 생성합니다"
        )
        
        st.divider()
        
        # 시스템 프롬프트
        st.subheader("📝 시스템 프롬프트")
        system_prompt = st.text_area(
            "시스템 프롬프트",
            value=st.session_state.get("system_prompt", default_system_prompt),
            height=150,
            help="AI의 역할과 행동을 정의하는 프롬프트입니다"
        )
        
        st.divider()
        
        # 대화 초기화 버튼
        if st.button("🗑️ 대화 초기화", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        
        return model, temperature, system_prompt, False


def render_message(role: str, content: str):
    """
    개별 메시지 렌더링
    
    Args:
        role: 메시지 역할 (user 또는 assistant)
        content: 메시지 내용
    """
    if role == "user":
        with st.chat_message("user"):
            st.write(content)
    elif role == "assistant":
        with st.chat_message("assistant"):
            st.write(content)


def render_chat_messages(messages: list[dict]):
    """
    채팅 메시지 히스토리 렌더링
    
    Args:
        messages: 메시지 리스트 (role, content 포함)
    """
    for message in messages:
        render_message(message["role"], message["content"])


def render_streaming_response(placeholder, stream_generator):
    """
    스트리밍 응답 렌더링
    
    Args:
        placeholder: Streamlit placeholder 객체
        stream_generator: 텍스트 청크를 생성하는 제너레이터
        
    Returns:
        완성된 응답 텍스트
    """
    full_response = ""
    for chunk in stream_generator:
        full_response += chunk
        placeholder.markdown(full_response + "▌")
    
    placeholder.markdown(full_response)
    return full_response
