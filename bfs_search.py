"""
BFS 후보 수집 — 추천 파이프라인의 첫 단계.

입력 도서(시드)에서 출발해 co-loan 그래프를 너비 우선 탐색하여
점수 계산 단계로 넘길 후보 도서들을 수집한다.

[파이프라인 위치]
    graph.pkl 로드 → BFS 후보 수집(이 모듈) → 점수 계산 → Top-N 추출

[자료구조]
    graph["nodes"]: dict[isbn → BookNode]
    graph["edges"]: dict[isbn → list[(neighbor_isbn, weight)]]  (무향 인접 리스트)

[시간 복잡도]
    O(V + E)  — V: 방문 노드 수, E: 방문한 간선 수
"""
from collections import deque
from dataclasses import dataclass, field

from models import BookNode
from storage import load_graph


@dataclass
class Candidate:
    """BFS로 발견한 후보 도서. 다음 단계(점수 계산)에 넘기는 데이터.

    Attributes:
        isbn: 후보 도서 ISBN
        depth: 시드로부터의 최단 거리 (1 = 시드의 직접 이웃)
        total_weight: 시드들로부터 도달한 모든 경로의 co-loan 가중치 합
        paths_count: 시드들로부터 도달한 (최단 거리 기준) 경로 수
        book: 메타 정보 (제목, 저자, 키워드 등)
    """
    isbn: str
    depth: int
    total_weight: int = 0
    paths_count: int = 0
    book: BookNode = field(default=None)


def bfs_candidates(
    graph: dict,
    seed_isbns: list[str],
    max_depth: int = 2,
    exclude_seeds: bool = True,
    require_loan_info: bool = False,
) -> list[Candidate]:
    """시드 ISBN들에서 시작해 BFS로 max_depth 이내의 후보 도서를 수집한다.

    Args:
        graph: {"nodes": dict, "edges": dict} 형태의 그래프
        seed_isbns: 시작점 ISBN 리스트 (사용자가 읽은 도서들)
        max_depth: 탐색 깊이 한계 (1 = 직접 이웃만, 2 = 이웃의 이웃까지)
        exclude_seeds: True면 시드 자신은 결과에서 제외
        require_loan_info: True면 loan_count=0(보강 안 된 leaf 노드)은 후보에서 제외.
            그래프 빌드 단계에서 expand 안 된 노드는 메타 정보가 부실해 점수
            계산이 왜곡될 수 있다. 안전망이 필요할 때 켠다. (BFS traversal 자체에는
            영향 없음 — 결과 필터링만 한다)

    Returns:
        후보 리스트. depth 오름차순 → total_weight 내림차순으로 정렬.
        다음 단계(점수 계산)는 이 리스트를 받아 ranking을 매긴다.
    """
    nodes = graph["nodes"]
    edges = graph["edges"]
    seed_set = set(seed_isbns)

    # 그래프에 존재하는 시드만 사용 (없는 ISBN은 BFS 시작점이 될 수 없음)
    valid_seeds = [s for s in seed_isbns if s in nodes]
    if not valid_seeds:
        return []

    # ── BFS 초기화 ─────────────────────────────────────────────
    # visited[isbn] = {"depth": int, "weight": int, "paths": int}
    # depth는 시드로부터 발견된 최단 거리. 이후 같은 depth에서 재도달하면
    # weight/paths만 누적, 더 깊은 경로는 무시(BFS의 최단경로 특성).
    visited: dict[str, dict] = {}
    queue: deque[tuple[str, int]] = deque()

    for seed in valid_seeds:
        visited[seed] = {"depth": 0, "weight": 0, "paths": 1}
        queue.append((seed, 0))

    # ── BFS 본체 ───────────────────────────────────────────────
    while queue:
        current, depth = queue.popleft()

        # 깊이 한계 도달 — 더 확장하지 않음 (이웃은 발견 X)
        if depth >= max_depth:
            continue

        for neighbor, weight in edges.get(current, []):
            new_depth = depth + 1

            if neighbor not in visited:
                # 처음 방문 — 큐에 추가
                visited[neighbor] = {
                    "depth": new_depth,
                    "weight": weight,
                    "paths": 1,
                }
                queue.append((neighbor, new_depth))
            elif visited[neighbor]["depth"] == new_depth:
                # 같은 최단 거리로 재도달 — 가중치/경로 수 누적
                visited[neighbor]["weight"] += weight
                visited[neighbor]["paths"] += 1
            # else: 이미 더 짧은 경로로 발견됨 → 무시 (BFS 최단경로 특성)

    # ── 결과 구성 ──────────────────────────────────────────────
    candidates: list[Candidate] = []
    for isbn, info in visited.items():
        if exclude_seeds and isbn in seed_set:
            continue
        book = nodes.get(isbn)
        # require_loan_info: 보강 안 된 leaf 노드(loan_count=0)는 제외 — 점수 왜곡 방지
        if require_loan_info and (book is None or book.loan_count == 0):
            continue
        candidates.append(Candidate(
            isbn=isbn,
            depth=info["depth"],
            total_weight=info["weight"],
            paths_count=info["paths"],
            book=book,
        ))

    # 정렬: depth 오름차순 (가까운 노드 우선) → weight 내림차순
    candidates.sort(key=lambda c: (c.depth, -c.total_weight))
    return candidates


# ── 간단 사용 예시 (모듈 단독 실행 시) ──────────────────────────────
if __name__ == "__main__":
    import sys

    graph = load_graph("data/graph.pkl")
    print(f"그래프 로드: 노드 {len(graph['nodes']):,} / "
          f"엣지 {sum(len(v) for v in graph['edges'].values())//2:,}")

    # CLI 인자로 ISBN 받기 (없으면 첫 번째 시드로 데모)
    if len(sys.argv) > 1:
        seeds = sys.argv[1:]
    else:
        seeds = [next(iter(graph["nodes"]))]
        print(f"(데모 모드) 시드 도서: {seeds[0]}")

    # 시드 정보 출력
    for s in seeds:
        b = graph["nodes"].get(s)
        if b:
            print(f"  시드: {s} | {b.title[:50]}")
        else:
            print(f"  시드: {s} (그래프에 없음)")

    # BFS 실행
    candidates = bfs_candidates(graph, seeds, max_depth=2)
    print(f"\nBFS 후보 {len(candidates):,}개 수집 완료\n")

    # 상위 20개 미리 보기
    print(f"{'depth':>5} {'weight':>8} {'paths':>5}  ISBN            제목")
    for c in candidates[:20]:
        title = (c.book.title if c.book else "")[:50]
        print(f"{c.depth:>5} {c.total_weight:>8} {c.paths_count:>5}  {c.isbn}  {title}")
