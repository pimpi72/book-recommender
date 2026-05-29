# recommender.py
# BFS → 필터링 → 점수 계산 → Top-N 추출을 순서대로 실행한다
# 같은 입력으로 다시 호출하면 저장해둔 결과를 바로 반환한다 (캐싱)

import bfs_search
import filter as filter_module
import scorer as scorer_module


# 캐시: 같은 요청이 들어오면 다시 계산하지 않고 여기서 꺼낸다
# 키: (읽은 책 목록, 제외 책 목록, depth, top_n)
# 값: 추천 결과 리스트
cache = {}


def recommend(graph, seed_isbns, disliked_isbns, max_depth, top_n):
    # 캐시 키 생성 (리스트는 키로 못 쓰니까 tuple로 변환)
    cache_key = (tuple(sorted(seed_isbns)), tuple(sorted(disliked_isbns)), max_depth, top_n)

    # 이미 계산한 결과가 있으면 바로 반환
    if cache_key in cache:
        return cache[cache_key]

    # 1단계: BFS로 후보 수집
    candidates = bfs_search.bfs_candidates(graph, seed_isbns, max_depth=max_depth, exclude_seeds=True)

    # 2단계: 읽은 책, 싫어하는 책 제거
    candidates = filter_module.filter_candidates(candidates, set(seed_isbns), disliked_isbns)

    # 3단계: 점수 계산
    scored = scorer_module.score_candidates(candidates)

    # 4단계: 상위 N권 추출
    result = scorer_module.top_n_heap(scored, top_n)

    # 결과 저장
    cache[cache_key] = result

    return result