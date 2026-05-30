# scorer.py
# 후보 도서에 점수를 매기고 상위 N권을 뽑는다
#
# 점수 공식: (공동 대출 횟수 / log(전체 대출 수 + e)) * (1 / depth)
# - 공동 대출 횟수가 많을수록 점수가 높아짐
# - 전체 대출 수에 log 정규화: 인기 보정은 하되 너무 강하지 않게
#   (이전 weight/loan_count 공식은 인기책을 과도하게 페널티 → niche 책이 상위 독점하는 문제)
# - depth가 작을수록 (시드와 가까울수록) 점수가 높아짐

import heapq
import math


# 점수 계산 결과를 담는 클래스
class ScoredBook:
    def __init__(self, isbn, score, depth, total_weight, candidate):
        self.isbn = isbn
        self.score = score
        self.depth = depth
        self.total_weight = total_weight
        self.candidate = candidate  # 원본 Candidate 객체 (제목, 저자 등 포함)


def score_candidates(candidates):
    scored = []

    for candidate in candidates:
        # 도서 메타 정보가 없거나 대출 수가 0이면 1로 처리
        # (log(1+e) ≈ 1.31 정도로 부드럽게 처리됨 — 점수 인플레이션 없음)
        if candidate.book and candidate.book.loan_count > 0:
            loan_count = candidate.book.loan_count
        else:
            loan_count = 1

        # log 정규화로 인기 보정 — 인기책도 합리적인 점수
        score = (candidate.total_weight / math.log(loan_count + math.e)) * (1 / candidate.depth)

        scored.append(ScoredBook(
            isbn=candidate.isbn,
            score=score,
            depth=candidate.depth,
            total_weight=candidate.total_weight,
            candidate=candidate,
        ))

    return scored


def top_n_heap(scored, n):
    # heapq.nlargest: 전체 정렬 없이 상위 n개만 뽑아냄 (더 빠름)
    return heapq.nlargest(n, scored, key=lambda x: x.score)
