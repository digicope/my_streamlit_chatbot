# 11번 노트북 소스 설명 — Smart Factory Safety Agent

> 대상 파일: `11_smart_factory_safety_agent.ipynb`  
> 한 줄 요약: **CCTV 설비 이미지 → 위험 인식 → 유사 사고·안전 매뉴얼 검색 → 점검 보고서** 를 자동으로 만드는 AI Agent 실습입니다.

---

## 1. 이 노트북이 하는 일 (비유로 이해하기)

공장 CCTV에 작업자와 기계가 함께 찍혀 있다고 가정해 보세요.

1. **Vision AI**가 “사람이 기계에 너무 가깝다 / 겹친다”를 판단합니다.
2. **유사 사례 검색**으로 “예전에 비슷한 사고가 있었는지”를 찾습니다.
3. **안전 매뉴얼**에서 “이럴 때 어떻게 조치하는지”를 찾습니다.
4. 위 결과를 모아 **점검 보고서(Markdown)** 를 작성합니다.

사람이 직접 검색·보고서를 쓰는 대신, **Agent가 Tool을 순서대로 호출**해 같은 일을 합니다.

```
설비 이미지(CCTV PNG)
        ↓
위험 인식 (끼임/근접/안전)
        ↓
Agent가 Tool 호출
  ├─ search_similar_cases  (비슷한 사고 이미지)
  └─ search_safety_manual  (안전 절차 문서)
        ↓
종합 판단 → Markdown 보고서 저장
```

---

## 2. 꼭 알아둘 용어

| 용어 | 쉬운 설명 |
|------|-----------|
| **RAG** | 질문에 맞는 자료를 먼저 찾고, 그 자료를 보고 답하는 방식 |
| **Visual RAG** | 찾을 대상이 텍스트가 아니라 **이미지**인 RAG |
| **임베딩** | 이미지·문장을 AI가 비교할 수 있는 **숫자 배열(벡터)** 로 바꾸는 것 |
| **ChromaDB** | 벡터를 저장해 두고 “비슷한 것”을 찾아주는 로컬 DB |
| **SigLIP2** | 이미지와 한글 텍스트를 **같은 공간**의 벡터로 만드는 모델 |
| **bbox** | 사람·기계를 감싸는 **네모 상자** 좌표 |
| **IoU** | 두 네모가 얼마나 겹치는지 (0~1). 클수록 끼임 위험 ↑ |
| **Agent / Tool** | Agent는 “무엇을 할지” 정하고, Tool은 실제 검색·인식 함수 |
| **Plan → Act → Report** | 계획 → Tool 실행 → 보고서 작성 루프 |

---

## 3. 사전 준비

| 항목 | 내용 |
|------|------|
| 데이터 | AI Hub `smart_factory_human_accident.zip` → 프로젝트 루트 |
| 패키지 | `pip install -r conveyor_analyze/requirements.txt` |
| GPU | 유사 사례·매뉴얼·보고서만이면 **GPU 없이도 가능** |
| 선택 | `USE_QWEN=True`면 Qwen3-VL로 장면 설명 추가 (GPU 권장) |

주요 경로:

| 경로 | 역할 |
|------|------|
| `data/smart_factory/` | 압축 해제된 CCTV·라벨 |
| `data/smart_factory/chroma_db/` | 유사 사고 벡터 DB |
| `data/agent/safety_manual.json` | 안전 매뉴얼 청크 |
| `data/agent/reports/` | 생성된 점검 보고서 |

---

## 4. 노트북 구조 (섹션별)

| 섹션 | 무엇을 하나 |
|------|-------------|
| **0. 환경 설정** | import, 경로, `USE_QWEN`, `TOP_K` |
| **1. 데이터셋** | ZIP 해제, PNG+JSON 사례 목록(`CASE_INDEX`) 만들기 |
| **2. Vector DB** | `AccidentCaseStore` — SigLIP2 + ChromaDB |
| **3. 안전 매뉴얼** | `SafetyManualStore` — 키워드 + 의미 검색 |
| **4. Vision AI** | bbox IoU·거리로 위험도 추론 |
| **5. Tool Schema** | Agent가 부를 함수 목록 정의 |
| **6. Orchestrator** | Plan → Act → Report |
| **7. 시나리오** | 성형기·밀링기·사출기 점검 실행 |
| **8. (선택) Qwen** | VLM으로 장면 설명 강화 |

---

## 5. 핵심 소스 설명

### 5.1 환경 설정 셀

```python
ROOT = Path(".").resolve()
ZIP_PATH = ROOT / "smart_factory_human_accident.zip"
DATA_ROOT = ROOT / "data" / "smart_factory"
CHROMA_DIR = DATA_ROOT / "chroma_db"
USE_QWEN = True   # False면 Qwen 없이 bbox만으로 위험 인식
TOP_K = 3         # 유사 사례·매뉴얼 Top-3
```

- `ROOT`: 노트북이 있는 프로젝트 루트
- `sys.path`에 `conveyor_analyze`를 넣어 `SigLIP2Encoder`를 불러옵니다

### 5.2 ZIP 해제 & 사례 인덱스

| 함수 | 역할 |
|------|------|
| `data_is_ready()` | PNG·JSON이 이미 있는지 확인 |
| `extract_zip()` | ZIP을 CP949 한글 경로로 안전하게 해제 |
| (사례 스캔 로직) | 이미지·라벨 쌍에서 설비·사고유형·경로 메타 추출 |

결과물인 `CASE_INDEX` / `CASE_BY_ID`는 “이 이미지 ID가 어떤 설비·사고인지” 사전입니다.

### 5.3 `AccidentCaseStore` — 유사 사고 검색

```python
class AccidentCaseStore:
    def build_index(...)   # 이미지 → SigLIP2 벡터 → ChromaDB 저장
    def search_by_image(...)  # 쿼리 이미지와 비슷한 사고 Top-k
    def search_by_text(...)   # 한글 문장으로도 검색 가능
```

초보자 관점:

1. 사고 사진마다 “지문(벡터)”을 만듭니다
2. DB에 저장합니다
3. 새 사진이 오면 지문이 비슷한 과거 사고를 꺼냅니다

### 5.4 `SafetyManualStore` — 매뉴얼 검색

실무에서는 PDF를 RAG로 검색하지만, 이 실습은 `safety_manual.json` 청크를 씁니다.

점수 계산 아이디어:

- **키워드 점수(60%)**: 질문에 나온 단어가 청크에 얼마나 있는가
- **의미 점수(40%)**: SigLIP2 텍스트 임베딩 코사인 유사도
- 둘을 섞어 Top-k 절차를 반환합니다

### 5.5 Vision AI — bbox로 위험 판단

| 함수 | 역할 |
|------|------|
| `parse_label_objects()` | 라벨 JSON에서 사람(`h…`)·설비(`m…`) 네모 추출 |
| `bbox_iou()` | 두 네모 겹침 비율 |
| `infer_spatial_relationships()` | 겹침→high(끼임), 가까움→medium, 멀면→low |
| `HazardRecognizer.recognize()` | 위 결과를 위험 요약 dict로 반환 |

직관:

- **겹친다(IoU 큼)** → 끼임 위험 높음
- **가깝다** → 주의
- **멀다** → 비교적 안전

`visualize_hazard()`는 이미지 위에 초록(사람)·빨강(설비) 박스를 그려 확인합니다.

### 5.6 Tool Schema & `SafetyToolBox`

OpenAI function calling 형식으로 Tool을 정의합니다.

| Tool 이름 | 하는 일 |
|-----------|---------|
| `recognize_hazard` | 위험 인식 |
| `search_similar_cases` | 유사 사고 검색 |
| `search_safety_manual` | 안전 절차 검색 |

`SafetyToolBox`는 위 이름을 실제 Python 함수 호출로 연결하는 **실행기**입니다.

### 5.7 Agent Orchestrator

| 단계 | 함수 | 내용 |
|------|------|------|
| Plan | `plan_tools()` | 위험 결과에 맞춰 호출할 Tool 목록 결정 |
| Act | ToolBox 실행 | 인식 + 유사사례 + 매뉴얼 |
| Report | `llm_synthesize()` | 규칙 기반(또는 LLM)으로 종합 문장 작성 |
| 저장 | `agent.save_report()` | `data/agent/reports/`에 Markdown 저장 |

실습의 `llm_synthesize()`는 API 없이도 돌아가도록 **위험도 규칙**으로 판단문을 만듭니다. 실무에서는 GPT/Qwen API로 바꾸면 됩니다.

### 5.8 시나리오 실행

```python
SAMPLE_CASES = {
    "성형기": pick_sample("molding-machine"),
    "밀링기": pick_sample("milling-machine"),
    "사출기": pick_sample("injection-machine"),
}
result = agent.run(case_id)
```

설비 3종에 대해 Agent를 돌리고, 요약 표를 `pandas`로 확인합니다.

---

## 6. 실행 순서 (권장)

1. 환경 설정 셀 실행
2. ZIP 해제·사례 인덱스
3. ChromaDB 인덱싱 (처음 1회 시간 소요)
4. 매뉴얼·Vision AI·Tool·Agent 셀 순서대로
5. 시나리오에서 보고서 확인

---

## 7. 자주 겪는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| ZIP 없음 오류 | 데이터 미배치 | 루트에 zip 파일 두기 |
| 한글 폴더명 깨짐 | CP949 ZIP | 노트북의 `extract_zip` 재실행 |
| GPU 메모리 부족 | Qwen 로드 | `USE_QWEN = False` |
| 유사 검색이 비어 있음 | 인덱스 미구축 | `build_index` 셀 재실행 |

---

## 8. 이 노트북으로 남는 것

- **Agent = Tool을 조합해 업무를 자동화**하는 패턴
- Vision(위험) + Visual RAG(유사 사례) + 문서 RAG(매뉴얼) 결합
- 최종 산출물: `data/agent/reports/*.md` 점검 보고서

다음 단계로 **12번**(PDF 페이지 Visual RAG)을 보면 “문서 이미지”를 검색하는 다른 축을 배울 수 있습니다.
