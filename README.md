# Streamlit Web Chatbot

OpenAI API를 사용하는 대화형 웹 챗봇 애플리케이션입니다.

## 기능

- 💬 실시간 대화형 챗봇 인터페이스
- 🔄 스트리밍 응답 지원 (토큰 단위 실시간 표시)
- ⚙️ 사이드바 설정 (모델 선택, Temperature 조절)
- 📝 시스템 프롬프트 커스터마이징
- 💾 대화 히스토리 자동 저장 (세션 상태)
- 🛡️ 에러 처리 및 사용자 친화적 오류 메시지

## 기술 스택

- Python 3.11+
- Streamlit
- OpenAI (최신 SDK)
- python-dotenv

## 설치 및 실행

### 1. 저장소 클론 또는 파일 다운로드

```bash
cd Streamlit_Web_Chatbot
```

### 2. 가상환경 생성 및 활성화 (권장)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

`.env.example` 파일을 참고하여 `.env` 파일을 생성하고 OpenAI API 키를 설정하세요.

```bash
# .env 파일 생성
cp .env.example .env
```

`.env` 파일 내용:
```
OPENAI_API_KEY=sk-your-api-key-here
```

또는 환경변수로 직접 설정:
```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-your-api-key-here"

# macOS/Linux
export OPENAI_API_KEY="sk-your-api-key-here"
```

### 5. 애플리케이션 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속하면 챗봇을 사용할 수 있습니다.

## 프로젝트 구조

```
Streamlit_Web_Chatbot/
├── app.py                 # Streamlit 메인 엔트리 포인트
├── requirements.txt       # Python 의존성
├── .env.example          # 환경변수 템플릿
├── .env                  # 환경변수 (생성 필요)
├── README.md             # 프로젝트 문서
└── src/
    ├── llm.py            # OpenAI API 호출 및 스트리밍 처리
    ├── prompts.py        # 시스템 프롬프트 및 기본 설정
    ├── ui.py             # 채팅 UI 렌더링 함수
    └── utils.py          # 공통 유틸리티 (로깅, 에러 처리)
```

## 사용 방법

### 기본 사용

1. 사이드바에서 모델과 Temperature를 설정합니다.
2. 메인 영역의 입력창에 메시지를 입력하고 전송합니다.
3. AI의 응답이 스트리밍 방식으로 실시간 표시됩니다.

### 설정 옵션

- **모델**: 사용할 OpenAI 모델을 선택합니다 (예: gpt-4o-mini, gpt-4)
- **Temperature**: 0.0~1.0 사이의 값으로 응답의 창의성을 조절합니다
- **시스템 프롬프트**: AI의 역할과 행동을 정의하는 프롬프트를 수정할 수 있습니다
- **대화 초기화**: 현재 대화 히스토리를 모두 삭제합니다

## 환경변수

| 변수명 | 필수 | 설명 | 기본값 |
|--------|------|------|--------|
| `OPENAI_API_KEY` | ✅ | OpenAI API 키 | - |
| `OPENAI_MODEL` | ❌ | 기본 모델명 | `gpt-4o-mini` |

## 에러 처리

애플리케이션은 다음과 같은 오류 상황을 처리합니다:

- ❌ API 키 누락 또는 유효하지 않음
- ⏱️ API 호출 한도 초과 (Rate Limit)
- 🌐 네트워크 연결 오류
- ⏰ 요청 시간 초과 (Timeout)
- ❌ 기타 예상치 못한 오류

각 오류에 대해 사용자 친화적인 메시지가 표시됩니다.

## 배포 팁

### Streamlit Cloud 배포

1. GitHub에 프로젝트를 푸시합니다.
2. [Streamlit Cloud](https://streamlit.io/cloud)에 로그인합니다.
3. "New app"을 클릭하고 저장소를 선택합니다.
4. 환경변수 섹션에서 `OPENAI_API_KEY`를 추가합니다.
5. 배포를 시작합니다.

### 다른 플랫폼 배포

- **Heroku**: `Procfile`에 `web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0` 추가
- **Docker**: Streamlit 공식 이미지 사용
- **AWS/GCP/Azure**: 각 플랫폼의 컨테이너 서비스 활용

### 보안 주의사항

- ⚠️ `.env` 파일을 Git에 커밋하지 마세요 (`.gitignore`에 추가)
- ⚠️ API 키를 코드에 하드코딩하지 마세요
- ⚠️ 프로덕션 환경에서는 환경변수나 시크릿 관리 서비스를 사용하세요

## 라이선스

이 프로젝트는 자유롭게 사용할 수 있습니다.

## 문제 해결

### API 키 오류

- `.env` 파일이 프로젝트 루트에 있는지 확인
- API 키가 `sk-`로 시작하는지 확인
- 환경변수가 올바르게 로드되었는지 확인

### 모듈 import 오류

- `src/` 디렉토리가 올바른 위치에 있는지 확인
- Python 경로가 올바르게 설정되었는지 확인

### 스트리밍이 작동하지 않음

- OpenAI SDK가 최신 버전인지 확인: `pip install --upgrade openai`
- 네트워크 연결 상태 확인
