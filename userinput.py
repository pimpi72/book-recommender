# userinput.py
# 프로그램 시작점. 사용자 입력을 받고 추천 결과를 출력한다
# 실행: python userinput.py

import storage
import recommender


# 제목 키워드로 그래프에서 책을 검색한다
def search_by_title(graph, query):
    results = []

    for isbn, book in graph["nodes"].items():
        if query.lower() in book.title.lower():
            results.append({"isbn": isbn, "title": book.title, "author": book.author})
        if len(results) >= 5:
            break

    return results


# 책을 검색하고 번호로 선택하게 한다
# 빈 입력이면 None 반환 (입력 종료 신호)
def select_book(graph, prompt_msg):
    while True:
        query = input(prompt_msg).strip()

        if query == "":
            return None

        results = search_by_title(graph, query)

        if len(results) == 0:
            print("  검색 결과가 없어요. 다른 키워드로 다시 시도해보세요.\n")
            continue

        print()
        for i in range(len(results)):
            print(f"  {i+1}. {results[i]['title']} — {results[i]['author']}")
        print("  0. 다시 검색\n")

        choice = input("  번호를 선택하세요: ").strip()

        if choice == "0":
            continue

        if choice.isdigit() and 1 <= int(choice) <= len(results):
            selected = results[int(choice) - 1]
            print(f"  선택됨: {selected['title']}\n")
            return selected["isbn"]
        else:
            print("  올바른 번호를 입력해주세요.\n")


# 읽은 책과 싫어하는 책을 입력받는다
def get_user_input(graph):
    print("\n" + "=" * 50)
    print("  책 추천 시스템")
    print("=" * 50)

    # 읽은 책 입력
    print("\n[읽은 책 입력]")
    print("최근 읽은 책 제목을 검색해서 선택하세요. 끝나면 Enter\n")

    seed_isbns = []
    while True:
        isbn = select_book(graph, f"  책 검색 ({len(seed_isbns)}권 선택됨, 끝내려면 Enter): ")

        if isbn is None:
            if len(seed_isbns) == 0:
                print("  최소 한 권은 입력해야 해요.\n")
                continue
            break

        if isbn in seed_isbns:
            print("  이미 선택된 책이에요.\n")
        else:
            seed_isbns.append(isbn)

    # 싫어하는 책 입력 (선택 사항)
    print("\n[싫어하는 책 입력]")
    print("추천에서 제외할 책을 선택하세요. 없으면 Enter\n")

    disliked_isbns = set()
    while True:
        isbn = select_book(graph, f"  제외할 책 검색 ({len(disliked_isbns)}권 선택됨, 끝내려면 Enter): ")

        if isbn is None:
            break

        if isbn in disliked_isbns:
            print("  이미 선택된 책이에요.\n")
        else:
            disliked_isbns.add(isbn)

    return seed_isbns, disliked_isbns


# 메인 실행
graph = storage.load_graph("data/graph.pkl")

seed_isbns, disliked_isbns = get_user_input(graph)

results = recommender.recommend(
    graph,
    seed_isbns=seed_isbns,
    disliked_isbns=disliked_isbns,
    max_depth=2,
    top_n=5,
)

print(f"\n추천 도서 Top {len(results)}\n")
for i in range(len(results)):
    book = results[i].candidate.book
    print(f"  {i+1}. {book.title} — {book.author}  (점수: {results[i].score:.4f})")