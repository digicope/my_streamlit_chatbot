"""OpenAI API 호출 및 스트리밍 처리 모듈"""
import os
from typing import Optional, Iterator
import openai
from openai import OpenAI

from src.utils import format_error_message, validate_api_key, logger


class LLMClient:
    """OpenAI API 클라이언트 래퍼"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        LLMClient 초기화
        
        Args:
            api_key: OpenAI API 키 (없으면 환경변수에서 읽음)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        is_valid, error_msg = validate_api_key(self.api_key)
        
        if not is_valid:
            raise ValueError(error_msg)
        
        self.client = OpenAI(api_key=self.api_key)
    
    def stream_chat(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7
    ) -> Iterator[str]:
        """
        스트리밍 방식으로 채팅 응답 생성
        
        Args:
            messages: 대화 메시지 리스트 (OpenAI 포맷)
            model: 사용할 모델명
            temperature: 온도 파라미터
            
        Yields:
            응답 텍스트 청크
            
        Raises:
            Exception: API 호출 실패 시
        """
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except openai.AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise ValueError(format_error_message(e))
        except openai.RateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            raise ValueError(format_error_message(e))
        except openai.APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ValueError(format_error_message(e))
        except openai.APITimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise ValueError(format_error_message(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ValueError(format_error_message(e))
    
    def chat(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7
    ) -> str:
        """
        일반 방식으로 채팅 응답 생성 (스트리밍 없음)
        
        Args:
            messages: 대화 메시지 리스트 (OpenAI 포맷)
            model: 사용할 모델명
            temperature: 온도 파라미터
            
        Returns:
            완전한 응답 텍스트
            
        Raises:
            Exception: API 호출 실패 시
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
            
        except openai.AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise ValueError(format_error_message(e))
        except openai.RateLimitError as e:
            logger.error(f"Rate limit error: {e}")
            raise ValueError(format_error_message(e))
        except openai.APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            raise ValueError(format_error_message(e))
        except openai.APITimeoutError as e:
            logger.error(f"Timeout error: {e}")
            raise ValueError(format_error_message(e))
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise ValueError(format_error_message(e))
