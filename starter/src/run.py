"""Pipeline Day 06: đọc PDF → chunk → embedding → pgvector → benchmark top-3 cho ba cấu hình A/B/C.

Chạy từ thư mục starter/:
    python -m src.run                  # chạy cả dev và test
    python -m src.run --splits dev     # chỉ chạy dev (chưa đụng đến test)
"""
import argparse
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]  # thư mục starter/
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Tham số ba cấu hình. C dùng lại chỉ mục của B, chỉ khác ở bộ lọc metadata.
CONFIG = {
    "A": {"chunking": "fixed_size", "size": 500, "overlap": 50, "filter": False},
    "B": {"chunking": "by_paragraph", "max_size": 800, "filter": False},
    "C": {"chunking": "by_paragraph (dùng lại chỉ mục B)", "max_size": 800, "filter": True},
}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Chạy pipeline Day 06")
    parser.add_argument("--splits", default="dev,test", help="dev, test hoặc dev,test")
    parser.add_argument("--out", default=str(ROOT / "results"), help="thư mục lưu kết quả")
    args = parser.parse_args()
    splits = {item.strip() for item in args.splits.split(",") if item.strip()}
    if not splits or not splits <= {"dev", "test"}:
        sys.exit("--splits chỉ nhận dev, test hoặc dev,test")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        sys.exit("Thiếu DATABASE_URL: copy starter/.env.example thành starter/.env")
    model_name = os.getenv("EMBEDDING_MODEL") or DEFAULT_MODEL

    # 1. Đọc corpus theo manifest; ghi lại lỗi và trang rỗng (không bỏ qua im lặng).
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    pages = []
    ingestion_log = {"errors": [], "empty_pages": [], "pages_loaded": 0}
    for source in manifest["sources"]:
        try:
            loaded = load_pdf(
                ROOT / "data" / source["source_path_or_url"], source["source_id"],
                source["source_path_or_url"], pages=source["content_pages"],
                metadata={"category": source["category"], "language": source["language"]},
            )
        except Exception as error:  # ghi lỗi rồi dừng bên dưới nếu thiếu trang
            ingestion_log["errors"].append({"source_id": source["source_id"], "error": repr(error)})
            continue
        for page in loaded:
            if page.metadata["empty"]:
                ingestion_log["empty_pages"].append({"source_id": page.document_id, "page": page.page})
        pages += [page for page in loaded if not page.metadata["empty"]]
    ingestion_log["pages_loaded"] = len(pages)
    (out / "ingestion_log.json").write_text(
        json.dumps(ingestion_log, ensure_ascii=False, indent=2), encoding="utf-8")
    if ingestion_log["errors"] or len(pages) < 30:
        sys.exit(f"Corpus không đạt: {len(pages)} trang hợp lệ (cần ≥30), lỗi: {ingestion_log['errors']}")
    print(f"Corpus: {len(pages)} trang nội dung, {sum(len(p.text) for p in pages)} ký tự")

    # 2. Đọc benchmark (chỉ các split được chọn).
    benchmark = json.loads((ROOT.parent / "benchmark" / "questions.json").read_text(encoding="utf-8"))
    questions = [q for q in benchmark["questions"] if q["split"] in splits]
    print(f"Câu hỏi: {len(questions)} ({', '.join(sorted(splits))})")

    # 3. Embedding model thật + vector store; lỗi thì dừng, không dùng vector giả.
    embedder = MyEmbedder(model_name)
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()
    connection = psycopg.connect(database_url, autocommit=True)

    # 4. Tạo chunk, embedding và lưu cho A và B; kiểm tra nạp lại không nhân đôi.
    chunk_stats = {}
    for name in ("A", "B"):
        cfg = CONFIG[name]
        start = time.perf_counter()
        if name == "A":
            chunks = [c for p in pages for c in fixed_size(p, cfg["size"], cfg["overlap"])]
        else:
            chunks = [c for p in pages for c in by_paragraph(p, cfg["max_size"])]
        chunk_seconds = time.perf_counter() - start

        start = time.perf_counter()
        vectors = embedder.embed_documents([c.text for c in chunks])
        embed_seconds = time.perf_counter() - start

        start = time.perf_counter()
        store.upsert(name, chunks, vectors)
        store_seconds = time.perf_counter() - start
        count_first = connection.execute(
            "SELECT count(*) FROM chunks WHERE strategy = %s", (name,)).fetchone()[0]
        store.upsert(name, chunks, vectors)  # nạp lại cùng dữ liệu
        count_second = connection.execute(
            "SELECT count(*) FROM chunks WHERE strategy = %s", (name,)).fetchone()[0]

        lengths = [len(c.text) for c in chunks]
        chunk_stats[name] = {
            "chunks": len(chunks), "total_chars": sum(lengths),
            "len_min": min(lengths), "len_mean": round(statistics.mean(lengths), 1),
            "len_median": statistics.median(lengths), "len_max": max(lengths),
            "chunks_under_100_chars": sum(n < 100 for n in lengths),
            "chunk_seconds": round(chunk_seconds, 3), "embed_seconds": round(embed_seconds, 3),
            "store_seconds": round(store_seconds, 3),
            "rows_after_first_ingest": count_first, "rows_after_reingest": count_second,
        }
        print(f"{name}: {len(chunks)} chunk | embed {embed_seconds:.1f}s | "
              f"nạp lại: {count_first} → {count_second} dòng")
    chunk_stats["C"] = {"note": "C dùng lại chỉ mục và chunk của B; chỉ thêm bộ lọc khi câu hỏi có filter."}
    (out / "chunk_stats.json").write_text(
        json.dumps(chunk_stats, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. Chạy cùng câu hỏi cho ba cấu hình, lưu trace top-3 đầy đủ.
    traces = []
    for question in questions:
        start = time.perf_counter()
        query_vector = embedder.embed_query(question["question"])
        embed_ms = (time.perf_counter() - start) * 1000
        for name, index, applied_filter in (
            ("A", "A", None),
            ("B", "B", None),
            ("C", "B", question["filter"]),  # C chỉ lọc khi câu hỏi có filter
        ):
            start = time.perf_counter()
            hits = store.search(index, query_vector, 3, applied_filter)
            search_ms = (time.perf_counter() - start) * 1000
            trace = evaluate_query(question, hits)
            trace.update({
                "strategy": name, "index": index, "applied_filter": applied_filter,
                "embed_query_ms": round(embed_ms, 2), "search_ms": round(search_ms, 2),
            })
            traces.append(trace)
    connection.close()

    with open(out / "traces.jsonl", "w", encoding="utf-8") as file:
        for trace in traces:
            file.write(json.dumps(trace, ensure_ascii=False) + "\n")

    # 6. Tổng hợp và lưu cấu hình chạy để tái lập.
    summary = summarize(traces)
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    installed = {d.metadata["Name"].lower(): d.version for d in importlib_metadata.distributions()}

    with psycopg.connect(database_url) as check:
        server = check.execute("SELECT current_setting('server_version')").fetchone()[0]
        extension = check.execute(
            "SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()[0]
    run_config = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "splits_run": sorted(splits),
        "embedding": {"provider": "sentence-transformers (local, CPU)", "model": model_name,
                      "dimensions": embedder.dimensions, "normalized": True,
                      "query_vs_document": "cùng cách mã hoá, không dùng tiền tố"},
        "vector_store": {"name": "PostgreSQL + pgvector", "postgres": server, "pgvector": extension,
                         "metric": "cosine", "search": "exact (không dùng index xấp xỉ)"},
        "strategies": CONFIG,
        "top_k": 3,
        "cost_usd": 0,
        "versions": {"python": platform.python_version(), "os": platform.platform(),
                     **{package: installed.get(package, "không có") for package in
                        ("sentence-transformers", "torch", "psycopg", "pypdf", "python-dotenv")}},
        "seed": "không cần (không có bước ngẫu nhiên)",
        "mean_query_ms": {name: round(statistics.mean(
            t["embed_query_ms"] + t["search_ms"] for t in traces if t["strategy"] == name), 2)
            for name in ("A", "B", "C")},
    }
    (out / "run_config.json").write_text(
        json.dumps(run_config, ensure_ascii=False, indent=2), encoding="utf-8")

    # 7. In bảng kết quả (số tử/mẫu).
    print("\nKết quả (tử/mẫu):")
    for name in ("A", "B", "C"):
        for split in sorted(splits):
            g = summary[name][split]
            line = (f"  {name} | {split:4} | Hit@1 {g['hit_at_1']}/{g['questions']} | "
                    f"Hit@3 {g['hit_at_3']}/{g['questions']}")
            if g["filter_questions"]:
                line += f" | top-3 theo filter {g['filter_ok']}/{g['filter_questions']}"
            print(line)
    print(f"\nĐã lưu kết quả vào {out}")


if __name__ == "__main__":
    main()
