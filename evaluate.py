"""
평가 모듈 — Link Prediction 방식 Hit Rate@K

[목적] 개인 대출 이력이 없는 환경에서 시스템의 추천 정확도를 정량 측정.

[방법]
  1. 전체 co-loan 엣지의 20%를 정답으로 숨김 (test edges)
  2. 나머지 80%로만 그래프 재구성 (train graph)
  3. 정답 쌍 (A, B) 마다 A를 시드로 추천 → B가 Top-K에 있으면 Hit
     (양방향 평가: B를 시드로도 시도)
  4. Hit 비율 = Hit Rate@K

[베이스라인]
  - 랜덤: 전체 책 중 무작위 K권
  - 인기순: loan_count 상위 K권 (시드 무관)
"""
import random
import time
from collections import defaultdict

from tqdm import tqdm

import storage
import recommender


# ── 데이터 분할 ────────────────────────────────────────────

def split_edges(graph: dict, test_ratio: float = 0.2, seed: int = 42):
    """엣지를 train / test로 분리.

    - 무작위 분할
    - 각 노드 최소 1개 엣지는 train에 유지 (시드 후보 보존)
    """
    random.seed(seed)

    # 모든 무방향 엣지 수집 (a < b로 정규화) + weight 함께
    edges_with_weight = {}
    for isbn_a, neighbors in graph["edges"].items():
        for isbn_b, w in neighbors:
            key = (min(isbn_a, isbn_b), max(isbn_a, isbn_b))
            if key not in edges_with_weight:
                edges_with_weight[key] = w

    all_edges = list(edges_with_weight.keys())
    random.shuffle(all_edges)

    n_test = int(len(all_edges) * test_ratio)
    test_candidates = all_edges[:n_test]
    train_edges = all_edges[n_test:]

    # train degree 계산
    train_degree = defaultdict(int)
    for a, b in train_edges:
        train_degree[a] += 1
        train_degree[b] += 1

    # 고립 방지: test 엣지 중 한 쪽이라도 train에 없는 노드면 train으로 복귀
    final_test = []
    final_train = list(train_edges)
    for a, b in test_candidates:
        if train_degree[a] == 0 or train_degree[b] == 0:
            final_train.append((a, b))
            train_degree[a] += 1
            train_degree[b] += 1
        else:
            final_test.append((a, b))

    # train graph 재구성
    train_graph_edges = defaultdict(list)
    for a, b in final_train:
        w = edges_with_weight[(a, b)]
        train_graph_edges[a].append((b, w))
        train_graph_edges[b].append((a, w))

    train_graph = {
        "nodes": graph["nodes"],   # 노드 메타는 그대로 공유
        "edges": dict(train_graph_edges),
    }
    return train_graph, final_test


# ── 추천 시스템들 ─────────────────────────────────────────

def our_system_recommend(train_graph, seed_isbn, k):
    """우리 BFS + scorer 시스템."""
    try:
        results = recommender.recommend(
            train_graph,
            seed_isbns=[seed_isbn],
            disliked_isbns=set(),
            max_depth=2,
            top_n=k,
        )
        return [r.isbn for r in results]
    except Exception:
        return []


def random_recommend(train_graph, seed_isbn, k):
    """랜덤 K권 추천 (시드 제외)."""
    all_isbns = [i for i in train_graph["nodes"] if i != seed_isbn]
    return random.sample(all_isbns, min(k, len(all_isbns)))


# 인기순은 결과가 시드 무관 — 한 번 계산해서 캐시
_popularity_cache = None
def popularity_recommend(train_graph, seed_isbn, k):
    """loan_count 상위 K권 (시드 제외)."""
    global _popularity_cache
    if _popularity_cache is None:
        sorted_books = sorted(
            train_graph["nodes"].items(),
            key=lambda x: x[1].loan_count,
            reverse=True,
        )
        _popularity_cache = [isbn for isbn, _ in sorted_books]
    return [i for i in _popularity_cache if i != seed_isbn][:k]


# ── Hit Rate@K 평가 ──────────────────────────────────────

def evaluate_hit_rate(recommend_func, test_edges, k_values, label=""):
    """양방향 평가 — 같은 시드에 max(K) 한 번 호출하고 K별 슬라이스로 빠르게.

    Returns: {k: hit_rate} 딕셔너리
    """
    hits = {k: 0 for k in k_values}
    total = 0
    k_max = max(k_values)

    for a, b in tqdm(test_edges, desc=label, unit="edge"):
        # A를 시드로 → B 잡나
        topk_a = recommend_func(a, k_max)
        topk_a_set = {isbn: rank for rank, isbn in enumerate(topk_a)}
        for k in k_values:
            if b in topk_a_set and topk_a_set[b] < k:
                hits[k] += 1
        total += 1

        # B를 시드로 → A 잡나
        topk_b = recommend_func(b, k_max)
        topk_b_set = {isbn: rank for rank, isbn in enumerate(topk_b)}
        for k in k_values:
            if a in topk_b_set and topk_b_set[a] < k:
                hits[k] += 1
        total += 1

    return {k: hits[k] / total if total else 0.0 for k in k_values}


# ── 메인 ────────────────────────────────────────────────

def main():
    print("그래프 로드 중...")
    graph = storage.load_graph("data/graph.pkl")
    n_edges = sum(len(v) for v in graph["edges"].values()) // 2
    print(f"  노드 {len(graph['nodes']):,} / 엣지 {n_edges:,}")

    print("\nEdge split (test 20%)...")
    train_graph, test_edges = split_edges(graph, test_ratio=0.2, seed=42)
    train_edge_count = sum(len(v) for v in train_graph["edges"].values()) // 2
    print(f"  train 엣지: {train_edge_count:,}")
    print(f"  test 엣지:  {len(test_edges):,}")
    print(f"  양방향 평가 호출 수: {len(test_edges) * 2:,}")

    K_values = [5, 10]
    results = {}

    # 베이스라인은 빠름
    for name, func in [
        ("랜덤", random_recommend),
        ("인기순", popularity_recommend),
    ]:
        print(f"\n[{name}] 평가 중...")
        recommender.cache.clear()
        start = time.time()
        rec_func = lambda seed, k, f=func: f(train_graph, seed, k)
        results[name] = evaluate_hit_rate(rec_func, test_edges, K_values, label=name)
        print(f"  소요: {time.time()-start:.1f}초")

    # 우리 시스템 — 시간 걸림
    print(f"\n[우리 시스템] 평가 중... (시간 걸림)")
    recommender.cache.clear()
    start = time.time()
    rec_func = lambda seed, k: our_system_recommend(train_graph, seed, k)
    results["우리 시스템"] = evaluate_hit_rate(rec_func, test_edges, K_values, label="ours")
    print(f"  소요: {time.time()-start:.1f}초")

    # 결과 표
    print("\n" + "=" * 50)
    print(f"{'시스템':<15} {'Hit Rate@5':>15} {'Hit Rate@10':>15}")
    print("=" * 50)
    for name, row in results.items():
        print(f"{name:<15} {row[5]:>15.4f} {row[10]:>15.4f}")
    print("=" * 50)

    # 향상 비율
    print("\n베이스라인 대비 우리 시스템 향상:")
    for k in K_values:
        ours = results["우리 시스템"][k]
        rand = results["랜덤"][k]
        pop = results["인기순"][k]
        rand_ratio = ours / rand if rand > 0 else float("inf")
        pop_ratio = ours / pop if pop > 0 else float("inf")
        print(f"  Hit@{k:>2}: 랜덤 대비 {rand_ratio:>6.1f}배 | 인기순 대비 {pop_ratio:>5.2f}배")


if __name__ == "__main__":
    main()
