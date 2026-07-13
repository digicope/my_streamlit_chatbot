# 14번 노트북 소스 설명 — 이송장치 센서 시계열 RAG

> 대상 파일: `14_conveyor_timeseries_rag.ipynb`  
> 한 줄 요약: **시간에 따른 센서·상태 변화를 한글 문장으로 요약**해 검색하고, 필요하면 **같은 구간의 열화상**과 묶어 Qwen으로 분석합니다.

---

## 1. 이 노트북이 하는 일 (비유로 이해하기)

13번이 “이 순간의 열화상 사진”을 찾는다면,  
14번은 “**지난 30초 동안 온도가 계속 올랐던 구간**”처럼 **시간 구간**을 찾습니다.

1. 세션(한 번의 주행·측정) 안에서 센서 값을 시간순으로 이어 붙입니다.
2. 긴 줄을 **슬라이딩 윈도우**(예: 30초)로 자릅니다.
3. 각 구간을 `"NTC 29→32℃, CT1 최대 1.8A…"` 같은 **한글 요약 문장**으로 만듭니다.
4. 그 문장을 SigLIP2로 임베딩해 Qdrant에 넣습니다.
5. “CT1이 급상승한 구간”이라고 물으면 **비슷한 요약 문장**을 검색합니다.
6. (하이브리드) 그 구간의 **대표 열화상 PNG**를 붙여 Qwen이 종합 분석합니다.

```
Other/metadata EAV + 세션 시계열
        ↓
슬라이딩 윈도우 → 한글 요약 청크
        ↓
SigLIP2 텍스트 임베딩 → Qdrant (시계열 전용 컬렉션)
        ↓
한글 Query → 시계열 구간 Top-k
        ↓
동일 sample_id 열화상 연계 (13번 PNG)
        ↓
Qwen3-VL (요약 + 열화상)
```

---

## 2. 꼭 알아둘 용어

| 용어 | 쉬운 설명 |
|------|-----------|
| **Time-Series RAG** | 검색 단위가 한 이미지가 아니라 **시간 구간(윈도우)** |
| **세션** | AGV 한 번의 측정 묶음 (`TS_agv_01_…` 폴더) |
| **sample_id** | 한 시점 샘플 ID — 센서·메타·열화상을 **연결하는 열쇠** |
| **EAV** | Entity-Attribute-Value. 헤더 없는 `section,group,key,value` CSV |
| **trend** | 센서 변화 방향 (-1 하락, 0 유지, 1 상승) |
| **ir_max** | 열화상 픽셀 최대 온도 |
| **슬라이딩 윈도우** | 긴 시계열을 겹치며 자르는 기법 |
| **WINDOW_SIZE / STEP** | 창 길이 / 이동 간격 (예: 30 / 15 → 50% 겹침) |
| **하이브리드 RAG** | 시계열 hit + 열화상 이미지를 함께 쓰는 패턴 |

---

## 3. 사전 준비

| 항목 | 내용 |
|------|------|
| 데이터 | 13번과 동일 ZIP (`Conveyor_Condition_Monitoring.zip`) |
| 선행 | 13번에서 `thermal_images/`·`manifest.json`이 있으면 하이브리드가 더 풍부 |
| GPU | 검색만이면 상대적으로 가볍고, Qwen은 GPU 권장 |
| 캐시 | `timeseries_windows.json` — 윈도우 청크 재사용 |

주요 경로:

| 경로 | 역할 |
|------|------|
| `data/conveyor_condition_monitoring/` | 13번과 공유 |
| `Other/metadata/*.csv` | EAV (trend, ir_max, 외부온습도) |
| `thermal_images/` | 13번이 만든 PNG |
| `qdrant_db/` | DB 폴더는 공유, **컬렉션명은 분리** |
| `timeseries_windows.json` | 윈도우 요약 캐시 |

---

## 4. 13번·02번과의 관계

| 구분 | 02번 | 13번 | **14번** |
|------|------|------|----------|
| 데이터 | 가상 프레임 | 실측 BIN 스냅샷 | **세션 시계열 + metadata** |
| 검색 | 이미지 | 열화상 이미지 | **시계열 요약 텍스트** |
| 센서 | frame 1행 | sample 1행 | **윈도우 구간 추이·trend** |
| 컬렉션 | Chroma | 열화상 Qdrant | **시계열 전용 Qdrant** |

> 13번 = “사진으로 이상 찾기”  
> 14번 = “**시간 패턴**으로 이상 구간 찾기”

---

## 5. 노트북 구조 (섹션별)

| 섹션 | 무엇을 하나 |
|------|-------------|
| **0. 환경 설정** | `WINDOW_SIZE`, `MAX_SESSIONS`, 시계열 컬렉션명 |
| **ZIP 해제** | 데이터 없으면 자동 추출 |
| **1. 데이터 준비** | 레코드 스캔 (`sample_id` 중심) |
| **2. EAV 파싱** | trend·ir_max·외부센서 병합 |
| **3. 세션 DataFrame** | 시간순 시계열 테이블 |
| **4. EDA** | NTC·CT1·state 그래프 |
| **5. 윈도우 청크** | 한글 요약 문장 생성 |
| **6. 인덱싱** | SigLIP2 텍스트 → Qdrant |
| **7. 검색** | 한글 시계열 질의 |
| **8. 하이브리드** | hit ↔ 열화상 PNG |
| **9. Qwen** | 요약+이미지 분석 |
| **10. 통합** | `run_timeseries_rag()` |

---

## 6. 핵심 소스 설명

### 6.1 초보자가 만질 변수

| 변수 | 의미 | 팁 |
|------|------|----|
| `DEMO_MODE` | 세션·윈도우 수 제한 | 첫 실행 `True` |
| `MAX_SESSIONS` | DEMO 세션 수 | 4면 빠른 확인 |
| `WINDOW_SIZE` | 창 길이(샘플≈초) | 30 ≈ 30초 |
| `WINDOW_STEP` | 이동 간격 | 15면 절반 겹침 |
| `TS_COLLECTION_NAME` | 시계열 컬렉션명 | 13번 열화상과 **이름 다르게** |

### 6.2 `sample_id`가 연결 고리

같은 `sample_id`로 다음이 연결됩니다.

- 원천 센서 CSV (NTC, CT…)
- `Other/metadata/{sample_id}.csv` (trend, ir_max…)
- `thermal_images` / manifest의 열화상 PNG

시계열에서 구간을 찾은 뒤, 그 안의 sample로 **사진**을 꺼낼 수 있습니다.

### 6.3 `parse_metadata_eav()` — EAV CSV 읽기

헤더가 없는 4열 예시:

```
sensor_data,NTC,value,29.0
sensor_data,NTC,trend,1
ir_data,temp_max,value_TGmx,44.38
```

| 함수 | 역할 |
|------|------|
| `parse_metadata_eav()` | section/group/key → 중첩 dict |
| `enrich_record_from_metadata()` | wide CSV 레코드에 trend·ir_max 등 붙이기 |
| `sample_sort_key()` | sample_id에서 시간 정렬용 숫자 키 추출 |

### 6.4 `build_session_dataframe()`

- 세션별로 sample을 시간순 정렬
- DEMO면 `MAX_SESSIONS`개만 유지
- 결과: 행=시점, 열=NTC·CT·state·trend…

### 6.5 시계열 EDA

`plot_session_timeseries(df, session)`:

- 위: NTC(온도)
- 중: CT1(전류)
- 아래: state(정상~이상)

검색 전에 “데이터가 출렁이는지”를 눈으로 확인합니다.

### 6.6 슬라이딩 윈도우 → 한글 청크 (가장 중요한 아이디어)

긴 시계열 전체를 한 벡터로 넣으면 **어디가 문제인지** 찾기 어렵습니다.  
그래서 구간마다 **사람이 읽을 문장**을 만듭니다.

```python
summarize_window(win)  # 예:
# "세션 TS_..., 구간 08:12~08:12:29: NTC 29.0→32.1℃, CT1 최대 1.80A,
#  열화 상태 최고 경고, 열화상 최대 44.4℃, NTC 상승"
```

| 함수 | 역할 |
|------|------|
| `trend_text()` | trend 코드 → “NTC 상승” 등 |
| `summarize_window()` | 윈도우 → 검색용 한글 문장 |
| `build_window_chunks()` | 세션마다 size/step로 슬라이스 → chunk 목록 |

chunk에는 검색용 `text`뿐 아니라, 나중에 열화상을 찾기 위한 **sample_id 목록·세션·통계**도 들어갑니다.

### 6.7 SigLIP2 텍스트 인덱싱

13번은 **이미지**를 임베딩했지만,  
14번은 윈도우 **요약 문장(텍스트)** 만 임베딩합니다.

```python
index_windows_to_qdrant(...)  # 텍스트 벡터 + payload(세션, state peak 등)
```

컬렉션을 13번과 분리해, 열화상 검색과 시계열 검색이 섞이지 않게 합니다.

### 6.8 검색 & 하이브리드

| 함수 | 역할 |
|------|------|
| `search_timeseries_windows()` | 한글 질의 → 유사 윈도우 Top-k |
| `show_timeseries_hits()` | 요약 문장·점수 표 |
| `show_hybrid_hits()` | hit의 sample ↔ 열화상 PNG + 센서 차트 |

질의 작성 팁:

- 좋음: `"CT1 전류가 급상승한 구간"`, `"NTC가 계속 오른 세션"`
- 센서 이름·변화 방향·상태를 넣으면 매칭이 쉬워집니다

### 6.9 Qwen & 통합 파이프라인

| 함수 | 역할 |
|------|------|
| `release_siglip()` / `load_qwen()` | VRAM 교대 로드 |
| `analyze_timeseries_with_qwen()` | 요약 문장 + 대표 열화상으로 분석 |
| `run_timeseries_rag()` | 검색 → 하이브리드 시각화 → (선택) Qwen |

```python
run_timeseries_rag("NTC 온도 상승과 이상 상태", use_qwen=False)
```

---

## 7. 실행 순서 (권장)

1. 환경 설정  
2. ZIP 확인·해제  
3. 레코드 스캔 + EAV enrich  
4. 세션 DataFrame + EDA  
5. 윈도우 청크 생성(캐시)  
6. Qdrant 인덱싱  
7. 검색 → 하이브리드  
8. (선택) Qwen / `run_timeseries_rag()`  

---

## 8. 자주 겪는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| metadata 없음 | ZIP 미해제·경로 오류 | ZIP 셀·`METADATA_DIR` 확인 |
| 열화상 안 보임 | 13번 PNG 미생성 | 13번 섹션 3 실행 또는 하이브리드 생략 |
| 윈도우 0개 | 세션이 WINDOW_SIZE보다 짧음 | `WINDOW_SIZE` 줄이기 / 세션 늘리기 |
| 검색이 동떨어짐 | DEMO 세션 너무 적음 | `MAX_SESSIONS` 증가, `DEMO_MODE=False` |
| Qdrant lock | 중복 클라이언트 | Kernel Restart |

---

## 9. 11~14번 한눈에 정리

| 노트북 | 핵심 질문 | 검색 대상 |
|--------|-----------|-----------|
| **11** | 이 CCTV는 위험한가? 조치는? | 사고 이미지 + 매뉴얼 |
| **12** | 안전 매뉴얼에 뭐라고 되어 있나? | PDF 페이지 이미지 |
| **13** | 지금 열화상·센서가 이상인가? | 열화상 PNG + 센서 메타 |
| **14** | **언제** 센서가 나빠졌나? | 시계열 요약 구간 (+ 열화상) |

14번까지 마치면 **이미지 RAG · 문서 Visual RAG · 센서 스냅샷 RAG · 시계열 RAG** 네 가지 패턴을 모두 경험한 셈입니다.
