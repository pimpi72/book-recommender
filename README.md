# book-recommender

자료구조 수업 협업 과제 — **정보나루 co-loan 그래프 기반 도서 추천 시스템**.

"같이 빌린 책이 추천에 도움된다"는 원리를 그래프 자료구조로 구현하고, 자료구조 선택의 효율성과 추천 정확도를 정량적으로 평가한 프로젝트입니다.

---

## 시스템 개요

```
입력: 사용자가 읽은 책 ISBN
        ↓
[1] graph.pkl 로드
        ↓
[2] BFS 후보 수집 (depth=2)
        ↓
[3] 후보 필터링 (읽은 책, 싫어하는 책 제외)
        ↓
[4] 점수 계산 (log 정규화)
        ↓
[5] Top-N 추출 (Max-Heap)
        ↓
출력: 추천 도서 K권
```

---

## 파일 구성

| 파일 | 역할 |
|---|---|
| `userinput.py` | **진입점.** CLI 인터페이스, 사용자 입력 처리 |
| `recommender.py` | 파이프라인 오케스트레이션 + 캐싱 |
| `bfs_search.py` | BFS로 후보 도서 수집 (그래프 탐색) |
| `filter.py` | 읽은 책 / 싫어하는 책 제외 |
| `scorer.py` | 점수 계산 + Top-N 추출 (Max-Heap) |
| `storage.py` | `load_graph()` — pickle 그래프 로드 |
| `models.py` | `BookNode` 데이터클래스 (pickle 호환용) |
| `evaluate.py` | **평가 모듈** — Link Prediction Hit Rate@K |
| `data/graph.pkl` | 정보나루 co-loan 그래프 (4,461 노드 / 25,918 엣지) |
| `자료구조-비교실험.ipynb` | 자료구조 선택 벤치마크 (인접 행렬 vs 리스트, Heap vs 정렬) |

---

## 의존성

```
pip install tqdm
```

평가 모듈에 진행률 표시용. 나머지는 표준 라이브러리만 사용.

---

## 실행 방법

### 1) 대화형 추천 (CLI)

```
python userinput.py
```

읽은 책 제목으로 검색 → 번호 선택 → 추천 Top-5 출력.

### 2) 함수 호출로 통합

```python
import storage, recommender

graph = storage.load_graph("data/graph.pkl")
results = recommender.recommend(
    graph,
    seed_isbns=["9788925588735"],   # 프로젝트 헤일메리
    disliked_isbns=set(),
    max_depth=2,
    top_n=10,
)
for r in results:
    print(r.score, r.candidate.book.title)
```

### 3) 평가 실행

```
python evaluate.py
```

전체 엣지 20%를 정답으로 숨기고 80%로 학습 → Hit Rate@K 측정 (랜덤·인기순과 비교).

---

## 핵심 알고리즘

### BFS 후보 수집 — `bfs_search.py`

- `collections.deque` 기반 표준 BFS (FIFO 큐)
- visited dict로 노드별 `{depth, weight, paths}` 추적
- 같은 노드를 더 깊은 경로로 재방문하면 무시 (BFS 최단경로 특성 보존)
- 같은 최단 거리에서 재도달 시 weight/paths 누적
- **시간 복잡도: O(V + E)**

### 점수 공식 — `scorer.py`

$$\text{score} = \frac{\text{total\_weight}}{\ln(\text{loan\_count} + e)} \times \frac{1}{\text{depth}}$$

- **분자 (total_weight)**: 시드와의 co-loan 연관 강도
- **분모 (log normalize)**: 인기 보정. 선형 분모는 niche 책 과대평가 → log로 부드럽게
- **계수 (1/depth)**: 가까운 책 우선 (시드 직접 이웃이 두 배 우대)

### Top-N 추출 — `scorer.py`

`heapq.nlargest(N, scored, key=score)` — **O(N log K)** (전체 정렬 `O(N log N)` 회피)

---

## 평가 결과 (Hit Rate@K)

### 방법론

Link Prediction 평가 (논문 arXiv:2102.09185 참조):
1. 전체 엣지 25,918개 중 **20% (5,013개)를 정답으로 숨김** (test edges)
2. 나머지 80% (20,905 엣지)로만 그래프 재구성 (train graph)
3. 정답 쌍 (A, B) 마다 A를 시드로 추천 → Top-K에 B가 있으면 Hit
4. 양방향 평가로 신뢰도 ↑ (10,026회 시도)

### 결과

| 시스템 | Hit Rate@5 | Hit Rate@10 |
|---|---|---|
| 랜덤 추천 | 0.0011 | 0.0026 |
| 인기순 추천 | 0.0026 | 0.0156 |
| **우리 시스템** | **0.5305** | **0.6687** |

### 베이스라인 대비 향상

| | Hit@5 | Hit@10 |
|---|---|---|
| 랜덤 대비 | **483.5배** | **257.8배** |
| 인기순 대비 | **204.6배** | **42.97배** |

**→ Top-10 추천 안에 정답 co-loan 책이 약 3분의 2 확률(67%)로 포함됨.**

---

## 자료구조 선택 근거 (`자료구조-비교실험.ipynb`)

### 인접 행렬 vs 인접 리스트 (메모리)

| 자료구조 | 메모리 사용량 |
|---|---|
| 인접 행렬 (V × V) | 152.10 MB |
| 인접 리스트 (실제 엣지만) | 0.64 MB |
| **→ 인접 리스트가 약 236배 효율적** | |

이유: 우리 그래프는 매우 sparse — 가능한 엣지(4,461² ≈ 약 2천만) 대비 실제 25,918개로 **0.13%만 연결**.

### Max-Heap vs 전체 정렬 (Top-K 추출 속도)

| K | 전체 정렬 | Max-Heap | 속도 비 |
|---|---|---|---|
| 5 | 0.000621초 | 0.000185초 | **3.4배** |
| 10 | 0.000621초 | 0.000221초 | 2.8배 |
| 50 | 0.000621초 | 0.000225초 | 2.8배 |

이유: 전체 정렬 O(N log N) vs Heap Top-K O(N log K). K가 작을수록 Heap 우위.

---

## 데이터 출처

[정보나루(www.data4library.kr)](https://www.data4library.kr) Open API:
- `loanItemSrch` — KDC 장르별 인기 대출 도서 (시드 수집용)
- `usageAnalysisList` — 함께 대출된 도서 (co-loan 엣지)

3년간(2023~2026) 전국 도서관 대출 통계 기반. 시드 988권 + BFS 확장 3단계로 총 4,461권 수집.

---

## 한계 및 향후 과제

| 한계 | 설명 |
|---|---|
| **정확도 ≠ 만족도** | Hit Rate는 그래프 복원 정확도. 진짜 사용자 만족도는 user study 필요 |
| **데이터 출처 동일** | 학습/평가 모두 정보나루. 외부 ground truth 없음 |
| **Leaf 노드 약함** | degree 작은 책(예: 프로젝트 헤일메리) 시드는 후보 풀이 작음 |
| **scorer의 인기 보정** | log 완화에도 인기책 정답 일부는 놓칠 수 있음 |

---

## 역할 분담

| 단계 | 담당 |
|---|---|
| 데이터 수집 (그래프 빌드) | |
| BFS 후보 수집 (`bfs_search.py`) | |
| 점수 계산 / Top-N (`scorer.py`, `recommender.py`) | |
| 필터링 (`filter.py`) | |
| 사용자 인터페이스 (`userinput.py`) | |
| 평가 (`evaluate.py`) | |
| 자료구조 벤치마크 | |
