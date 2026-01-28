"""공통 유틸리티 함수"""
import logging
from typing import Optional

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def format_error_message(error: Exception) -> str:
    """
    예외를 사용자 친화적인 메시지로 변환
    
    Args:
        error: 발생한 예외
        
    Returns:
        사용자 친화적인 오류 메시지
    """
    error_type = type(error).__name__
    error_msg = str(error)
    
    # OpenAI API 관련 오류 처리
    if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
        return "❌ OpenAI API 키가 유효하지 않습니다. 환경변수 OPENAI_API_KEY를 확인해주세요."
    
    if "rate limit" in error_msg.lower():
        return "⏱️ API 호출 한도에 도달했습니다. 잠시 후 다시 시도해주세요."
    
    if "network" in error_msg.lower() or "connection" in error_msg.lower():
        return "🌐 네트워크 연결 오류가 발생했습니다. 인터넷 연결을 확인해주세요."
    
    if "timeout" in error_msg.lower():
        return "⏰ 요청 시간이 초과되었습니다. 다시 시도해주세요."
    
    # 일반적인 오류
    return f"❌ 오류가 발생했습니다: {error_msg}"


def validate_api_key(api_key: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    API 키 유효성 검사
    
    Args:
        api_key: 검사할 API 키
        
    Returns:
        (유효 여부, 오류 메시지)
    """
    if not api_key:
        return False, "OPENAI_API_KEY 환경변수가 설정되지 않았습니다."
    
    if not api_key.startswith("sk-"):
        return False, "OPENAI_API_KEY 형식이 올바르지 않습니다. 'sk-'로 시작해야 합니다."
    
    return True, None
