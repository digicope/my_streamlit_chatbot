# 12번 노트북 소스 설명 — KOSHA 안전보건 Visual RAG

> 대상 파일: `12_kosha_safety_health_visual_rag.ipynb`  
> 한 줄 요약: **KOSHA 안전 매뉴얼 PDF 페이지를 이미지로 검색**하고, **Qwen3-VL이 근거 페이지를 보고 한글 답변**을 만듭니다.

---

## 1. 이 노트북이 하는 일 (비유로 이해하기)

도서관에서 “지게차 전도 예방법은?”을 물어볼 때:

1. 사서(검색 모델)가 **관련 페이지 사진**을 찾아줍니다.
2. 전문가(생성 모델)가 그 **페이지를 읽고** 답합니다.

전통 RAG는 PDF를 OCR로 글자만 뽑지만, 안전 매뉴얼은 **표·아이콘·박스 레이아웃**이 중요합니다.  
그래서 이 노트북은 OCR 대신 **페이지 전체를 이미지로 보고 검색**합니다 (ColPali).

```
KOSHA PDF
   ↓ PyMuPDF
페이지 PNG
   ↓ ColPali (Multi-vector)
Qdrant 저장
   ↓ 한글 질문
관련 페이지 Top-k
   ↓ Qwen3-VL
근거 있는 한글 답변
```

---

## 2. 꼭 알아둘 용어

| 용어 | 쉬운 설명 |
|------|-----------|
| **Visual RAG** | 검색 대상이 **이미지(PDF 페이지 스크린샷)** 인 RAG |
| **Retriever / Generator** | 검색기(ColPali)와 답변기(Qwen3-VL)를 **역할 분리** |
| **ColPali** | PDF 페이지를 **패치(조각)마다 벡터**로 만드는 검색 모델 |
| **Multi-vector** | 문서 1장 = 벡터 1개가 아니라 **수백~천 개** |
| **MaxSim** | 질문 토큰과 페이지 패치를 쌍으로 맞춰 점수를 내는 방식 |
| **Qdrant** | Multi-vector + MaxSim을 지원하는 벡터 DB |
| **payload** | 벡터와 함께 저장하는 PDF 이름·페이지 번호 등 메타 |
| **manifest** | “어떤 PNG가 어떤 PDF 몇 페이지인지” 목록 JSON |
| **DEMO_MODE** | PDF·페이지 수를 줄여 **빠른 실습**하는 스위치 |

---

## 3. 사전 준비

| 항목 | 내용 |
|------|------|
| 데이터 | `KOSHA_Safety_Health.zip` → 프로젝트 루트 |
| GPU | ColPali + Qwen3-VL 권장 (CPU는 매우 느림) |
| 패키지 | `qdrant-client`, `pymupdf`, `transformers`, `torch`, `qwen-vl-utils` 등 |
| 첫 실행 | Hugging Face에서 모델 다운로드 (수 GB) |

주요 경로:

| 경로 | 역할 |
|------|------|
| `data/kosha/pdfs/` | 원본 PDF |
| `data/kosha/pages/` | 페이지 PNG (`doc_해시/page_0001.png`) |
| `data/kosha/pages_manifest.json` | 페이지 카탈로그 |
| `data/kosha/qdrant_db/` | ColPali 벡터 DB |

---

## 4. 노트북 구조 (섹션별)

| 섹션 | 무엇을 하나 |
|------|-------------|
| **0. 환경 설정** | 경로, `DEMO_MODE`, `TOP_K`, 모델 ID |
| **1. ZIP 해제** | CP949 한글 파일명 복원 후 PDF 추출 |
| **2. PDF → 이미지** | PyMuPDF로 페이지 PNG + manifest |
| **3. ColPali** | 페이지·질문 Multi-vector 임베딩 |
| **4. Qdrant** | MaxSim 컬렉션에 인덱싱 |
| **5. 검색** | 한글 질문 → 관련 페이지 |
| **6. Qwen3-VL** | 검색 페이지 기반 답변 |
| **7. 통합 파이프라인** | `visual_rag_kosha()` 한 번에 실행 |
| **8. 정리** | 개념 복습·트러블슈팅 |

---

## 5. 핵심 소스 설명

### 5.1 환경 설정에서 자주 쓰는 변수

| 변수 | 의미 | 초보자 팁 |
|------|------|-----------|
| `DEMO_MODE` | 소량 PDF만 사용 | 처음엔 `True` |
| `MAX_PAGES_PER_PDF` | PDF당 최대 페이지 | `None`이면 전체 |
| `REBUILD_INDEX` | DB·manifest 재생성 | PDF 바꿨으면 `True` |
| `TOP_K` | 검색에 쓸 페이지 수 | 3~5 |
| `COLPALI_BATCH_SIZE` | 한 번에 임베딩할 장 수 | OOM이면 `1` |
| `PDF_DPI` | 렌더링 해상도 | 기본 150 |

### 5.2 `decode_zip_filename()` — 한글 파일명 복원

Windows에서 만든 ZIP은 파일명이 **CP949**인 경우가 많습니다.  
Python이 UTF-8로 잘못 읽으면 `▒└┐`처럼 깨집니다.

```python
# 깨진 이름 → cp437로 되돌린 뒤 cp949로 다시 해석
name.encode("cp437").decode("cp949")
```

`extract_kosha_zip()`이 PDF만 골라 `data/kosha/pdfs/`에 정상 한글 이름으로 저장합니다.

### 5.3 `pdf_to_page_images()` — PDF를 사진으로

| 단계 | 코드 개념 |
|------|-----------|
| PDF 열기 | `fitz.open(pdf_path)` |
| DPI 확대 | `fitz.Matrix(dpi/72, dpi/72)` |
| 비트맵 | `page.get_pixmap(...)` |
| 저장 | `page_0001.png`, `page_0002.png` … |
| 목록 | manifest에 `doc_id`, `pdf_name`, `page_num`, `image_path` |

`safe_stem()`은 한글 경로 문제를 피하려고 **파일명 해시**로 `doc_a1b2c3…` 폴더를 만듭니다.

### 5.4 `ColPaliEncoder` — Multi-vector 임베딩

일반 이미지 검색(SigLIP2)은 **이미지 1장 → 벡터 1개**입니다.  
ColPali는 페이지를 **약 1,024개 패치**로 나누고, 패치마다 128차원 벡터를 만듭니다.

```
페이지 PNG ──→ [패치1, 패치2, … 패치1024]  (각각 128차원)
질문 텍스트 ──→ [토큰1, 토큰2, …]           (질문 길이만큼)
```

| 메서드 | 입력 | 출력 |
|--------|------|------|
| `encode_images()` | PIL 이미지 목록 | 페이지별 Multi-vector |
| `encode_queries()` | 한글 질문 목록 | 질문 Multi-vector |
| `unload()` | — | GPU 메모리 해제 (Qwen 로드 전) |

### 5.5 Qdrant 인덱싱

```python
# 핵심 설정 개념
multivector_config = MultiVectorConfig(comparator=MAX_SIM)
hnsw_config m=0   # 소규모 실습: 전수 MaxSim (근사 검색 끔)
```

- 포인트 1개 = PDF 페이지 1장
- `payload`에 PDF 이름·페이지·이미지 경로 저장 → 검색 후 원본 추적

**주의**: 로컬 Qdrant(`path=`)는 **클라이언트 1개만** 열 수 있습니다.  
`get_qdrant_client()` 싱글톤을 쓰고, `AlreadyLocked`면 **Kernel Restart** 하세요.

### 5.6 검색 & 답변

| 함수 | 역할 |
|------|------|
| `search_kosha_pages()` | 질문 → ColPali → Qdrant MaxSim → Top-k |
| `show_search_hits()` | 찾은 페이지를 matplotlib로 미리보기 |
| `run_qwen_vl()` | 이미지 + 프롬프트 → 한글 생성 |
| `answer_with_kosha_pages()` | 페이지별 요약 → 종합 답변 (VRAM 절약: 1장씩) |

답변 원칙: **문서에 보이는 내용만** 근거로 쓰고, 없는 내용은 추측하지 말라고 프롬프트에 명시합니다.

### 5.7 `visual_rag_kosha()` — 원버튼 파이프라인

```
질문
 → ColPali 로드(필요 시)
 → Top-k 검색 + 이미지 표시
 → ColPali unload (VRAM 확보)
 → Qwen 로드(필요 시)
 → 한글 답변
```

```python
visual_rag_kosha("지게차 충돌 예방은?", run_vlm=True)
visual_rag_kosha("질문", run_vlm=False)  # 검색만 빠르게
```

`EXTRA_QUERIES`에 주제별 질문 10개가 있어, 데모는 `[:3]`만 돌리도록 되어 있습니다.

---

## 6. 실행 순서 (권장)

1. 환경 설정  
2. ZIP 해제  
3. PDF → PNG + manifest  
4. ColPali 로드·샘플 임베딩 확인  
5. Qdrant 인덱싱 (`REBUILD_INDEX` 필요 시)  
6. 검색 테스트  
7. Qwen 답변 또는 `visual_rag_kosha()`  

---

## 7. 자주 겪는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| PDF 이름 깨짐 | CP949 ZIP | 섹션 1 재실행 |
| `AlreadyLocked` | Qdrant 중복 오픈 | Kernel Restart |
| CUDA OOM | ColPali+Qwen 동시 | ColPali `unload`, batch=1 |
| 검색이 이상함 | 인덱스 페이지 부족 | `DEMO_MODE=False`로 확대 |

---

## 8. 11번과의 차이 (한눈에)

| 구분 | 11번 Safety Agent | **12번 KOSHA** |
|------|-------------------|----------------|
| 데이터 | 공장 CCTV + 라벨 | 안전 매뉴얼 PDF |
| 검색 단위 | 사고 이미지 1장 | PDF **페이지 이미지** |
| 임베딩 | SigLIP2 (단일 벡터) | **ColPali Multi-vector** |
| 벡터 DB | ChromaDB | **Qdrant MaxSim** |
| 출력 | 점검 보고서 | Q&A 한글 답변 |

다음 **13번**은 PDF가 아니라 **열화상 + 실측 센서**로 Visual RAG를 합니다.
