# scorer.py
# 후보 도서에 점수를 매기고 상위 N권을 뽑는다
#
# 점수 공식: (공동 대출 횟수 / 전체 대출 수) * (1 / depth)
# - 공동 대출 횟수가 많을수록 점수가 높아짐
# - 전체 대출 수로 나누는 이유: 원래 인기 있는 책이 무조건 상위에 오는 걸 막기 위해
# - depth가 작을수록 (시드와 가까울수록) 점수가 높아짐

import heapq


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
        # 도서 메타 정보가 없거나 대출 수가 0이면 1로 처리 (0으로 나누면 에러)
        if candidate.book and candidate.book.loan_count > 0:
            loan_count = candidate.book.loan_count
        else:
            loan_count = 1

        score = (candidate.total_weight / loan_count) * (1 / candidate.depth)

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