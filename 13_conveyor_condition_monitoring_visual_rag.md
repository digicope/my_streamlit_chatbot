# 13번 노트북 소스 설명 — 이송장치 열화 예지보전 Visual RAG

> 대상 파일: `13_conveyor_condition_monitoring_visual_rag.ipynb`  
> 한 줄 요약: **열화상 이미지 + 실측 센서 + 열화 라벨**을 Qdrant에 넣고, 한글 질문으로 찾아 **Qwen3-VL이 이상·열화를 분석**합니다.

---

## 1. 이 노트북이 하는 일 (비유로 이해하기)

공장 이송장치(AGV·컨베이어)에 **열화상 카메라**와 **온도·전류·먼지 센서**가 붙어 있다고 생각해 보세요.

1. 과거 측정분을 DB에 “사진 + 센서 수치 + 정상/주의/경고/이상”으로 저장합니다.
2. “과열된 이상 패턴을 찾아줘”라고 물으면 **비슷한 열화상**을 검색합니다.
3. 찾은 이미지와 센서 값을 Qwen3-VL에 넘겨 **한글 분석문**을 받습니다.

이것이 **예지보전(고장 전에 징후를 보는 것)** 을 Visual RAG로 실습하는 노트북입니다.

```
Conveyor_Condition_Monitoring.zip
        ↓
EDA (상태·센서 분포 확인)
        ↓
BIN 열화상 → PNG + 센서 CSV + 라벨 JSON 매칭
        ↓
SigLIP2 임베딩 → Qdrant (벡터 + 메타)
        ↓
한글 Query → Top-k 열화상
        ↓
Qwen3-VL (열화상 + 센서 수치 분석)
```

---

## 2. 꼭 알아둘 용어

| 용어 | 쉬운 설명 |
|------|-----------|
| **예지보전** | 고장 나기 전 **이상 징후**를 보고 미리 조치 |
| **열화상 BIN** | 온도 값이 담긴 숫자 배열 파일 (120×160, ℃) |
| **state 0~3** | 0=정상, 1=주의, 2=경고, 3=이상 |
| **NTC** | 온도 센서 (℃) — 과열 징후 |
| **PM10** | 미세먼지 농도 (µg/m³) |
| **CT1~4** | 전류 센서 (A) — 과전류 징후 |
| **SigLIP2** | 열화상 PNG와 한글 질문을 같은 벡터 공간에 매핑 |
| **Qdrant** | 벡터 + 센서·state 메타를 저장·필터 검색 |
| **manifest** | 샘플별 PNG·센서·라벨 경로가 정리된 목록 |
| **DEMO_MODE** | 샘플 수를 줄여 빠른 실습 |

---

## 3. 사전 준비

| 항목 | 내용 |
|------|------|
| 데이터 | `Conveyor_Condition_Monitoring.zip` → 프로젝트 루트 |
| GPU | SigLIP2·Qwen 권장 |
| 패키지 | `qdrant-client`, `transformers`, `torch`, `pandas` 등 |
| 모듈 | `conveyor_analyze` (한글 matplotlib 등) |

주요 경로:

| 경로 | 역할 |
|------|------|
| `data/conveyor_condition_monitoring/` | 원천 데이터 루트 |
| `.../thermal_images/` | BIN→PNG 결과 |
| `.../qdrant_db/` | 벡터 DB |
| `.../manifest.json` | 샘플 카탈로그 |

---

## 4. 다른 노트북과의 차이

| 구분 | 02번 | 12번 | **13번** |
|------|------|------|----------|
| 데이터 | CCTV 프레임 | PDF 페이지 | **열화상 + 실측 센서** |
| 임베딩 | SigLIP2 | ColPali | **SigLIP2** |
| 벡터 DB | ChromaDB | Qdrant MaxSim | **Qdrant 코사인** |
| 메타 | 가상 sensor.csv | PDF·페이지 | **실측 NTC·CT + state** |

---

## 5. 노트북 구조 (섹션별)

| 섹션 | 무엇을 하나 |
|------|-------------|
| **0. 환경 설정** | 경로, `DEMO_MODE`, `MAX_SAMPLES`, 모델 ID |
| **1. ZIP 해제** | CP949 폴더명 복원, 세션 폴더 탐색 |
| **2. EDA** | state 분포, 센서 박스플롯, 상태별 열화상 미리보기 |
| **3. BIN→PNG** | 컬러맵 PNG + manifest 구축 |
| **4. 인덱싱** | SigLIP2 → Qdrant |
| **5. 검색** | 한글 텍스트로 열화상 Top-k |
| **6. Qwen3-VL** | 검색 결과 멀티모달 분석 |
| **7. 통합** | `run_conveyor_rag()` (+ state 필터) |

---

## 6. 핵심 소스 설명

### 6.1 환경 변수 (초보자가 자주 만지는 것)

| 변수 | 의미 | 팁 |
|------|------|----|
| `DEMO_MODE` | 샘플 수 제한 | 첫 실행 `True` |
| `MAX_SAMPLES` | DEMO 최대 장 수 | 800 ≈ 상태별 균등 |
| `REBUILD_INDEX` | Qdrant 재구축 | PNG·데이터 변경 시 |
| `TOP_K` | 검색·분석 상위 개수 | 3~5 |

`STATE_LABELS`로 숫자 라벨을 한글로 바꿉니다: `0→정상` … `3→이상`.

### 6.2 ZIP 해제 & 데이터 스캔

| 함수 | 역할 |
|------|------|
| `decode_zip_filename()` | CP949 한글 경로 복원 |
| `find_session_roots()` | `TS_`/`VS_`(센서), `TL_`/`VL_`(라벨) 세션 찾기 |
| `read_sensor_row()` | 샘플 CSV에서 NTC·PM·CT 읽기 |
| `load_label_state()` | JSON에서 state 읽기 |
| `scan_dataset_records()` | 샘플마다 경로·센서·라벨을 한 dict로 |

한 레코드 ≈ **한 시점의 열화상 + 센서 1행 + state**.

### 6.3 EDA — 왜 먼저 보나?

인덱싱 전에 “데이터가 어떻게 생겼는지”를 봅니다.

- state 0~3 개수 막대그래프
- NTC·CT 등 센서 박스플롯
- 상태별 열화상 1장씩 미리보기

이상 징후가 온도·전류와 어떻게 연결되는지 **눈**으로 익히는 단계입니다.

### 6.4 `thermal_bin_to_pil()` — BIN을 눈으로 보는 이미지로

```python
# 개념: float64 온도 배열(120×160) → inferno 컬러맵 → RGB PNG
arr = np.fromfile(bin_path, dtype=np.float64).reshape(120, 160)
# 정규화 후 colormap 적용 → PIL Image
```

사람은 숫자 배열보다 **색으로 표현된 열화상**을 이해하기 쉽고,  
SigLIP2도 PNG 이미지를 입력으로 받습니다.

`build_manifest()` / `convert_bins_to_png()`:

- 상태별 균등 샘플(`sample_manifest_stratified`) 가능
- PNG 저장 + `manifest.json` 기록

### 6.5 `SigLIP2Encoder` + Qdrant 인덱싱

| 함수/클래스 | 역할 |
|-------------|------|
| `SigLIP2Encoder.encode_images()` | PNG → 벡터 |
| `encode_texts()` | 한글 질문 → 같은 공간 벡터 |
| `ensure_siglip_collection()` | 코사인 유사도 컬렉션 생성 |
| `record_to_payload()` | sample_id, state, ntc, ct1 … 메타 |
| `index_manifest_to_qdrant()` | 배치로 벡터+payload upsert |

payload에 센서를 넣어 두면, 나중에 **“이상(state=3)만”** 같은 필터 검색이 가능합니다.

### 6.6 검색

```python
search_thermal_images(query, top_k=3, state_filter=None)
```

1. 질문을 SigLIP2 텍스트 벡터로 변환  
2. Qdrant에서 코사인 유사도 Top-k  
3. (선택) `state_filter="3"`이면 이상만  
4. `show_search_hits()`로 이미지·센서 표 표시  

### 6.7 Qwen3-VL 분석

VRAM이 부족하면 검색 모델과 생성 모델을 **동시에 올리지 않습니다**.

| 함수 | 역할 |
|------|------|
| `release_siglip()` | SigLIP2 메모리 해제 |
| `load_qwen()` | Qwen3-VL 로드 |
| `analyze_with_qwen()` | Top 이미지 + 센서 수치를 프롬프트에 넣어 분석 |

### 6.8 `run_conveyor_rag()` — 통합

```python
run_conveyor_rag("과열·열화 이상 징후", top_k=3, state_filter="3", use_qwen=False)
```

- `use_qwen=False`: 검색·차트만 (빠름)
- `use_qwen=True`: 분석문까지 (GPU 여유 필요)

---

## 7. 실행 순서 (권장)

1. 환경 설정  
2. ZIP 해제·레코드 스캔  
3. EDA  
4. BIN→PNG + manifest  
5. Qdrant 인덱싱  
6. 한글 검색  
7. (선택) Qwen / `run_conveyor_rag()`  

DEMO면 인덱싱이 수 분, 전체(~1만 장)면 GPU여도 더 깁니다.

---

## 8. 자주 겪는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| ZIP/폴더명 깨짐 | CP949 | 추출 셀 재실행 |
| Qdrant lock | 클라이언트 중복 | Kernel Restart |
| 인덱싱 너무 김 | 전체 데이터 | `DEMO_MODE=True` |
| OOM | SigLIP+Qwen 동시 | `release_siglip()` 후 Qwen |
| 열화상 없음 | BIN 미변환 | 섹션 3 재실행 |

---

## 9. 이 노트북으로 남는 것

- **이미지 + 실측 센서 메타**를 함께 넣는 Visual RAG
- state 필터로 “이상만 보기” 같은 **운영형 검색**
- 14번으로 이어지는 **시계열(시간 축) RAG**의 기반 데이터·PNG

다음 **14번**은 한 장 스냅샷이 아니라 **시간에 따른 센서 변화 구간**을 검색합니다.
