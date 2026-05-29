# filter.py
# 후보 도서 중에서 이미 읽은 책이나 싫어하는 책을 제거한다


def filter_candidates(candidates, read_isbns, disliked_isbns):
    result = []

    for candidate in candidates:
        # 이미 읽은 책이면 건너뜀
        if candidate.isbn in read_isbns:
            continue
        # 싫어하는 책이면 건너뜀
        if candidate.isbn in disliked_isbns:
            continue
        result.append(candidate)

    return result