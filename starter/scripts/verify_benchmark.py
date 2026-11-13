"""Kiểm chứng bộ benchmark trước khi chạy: evidence có thật ở trang gold không, split/filter có đủ không.

Chạy từ thư mục starter/:  python scripts/verify_benchmark.py
Chỉ đọc PDF và file câu hỏi; không ghi gì.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion import load_pdf  # noqa: E402


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
benchmark = json.loads((ROOT.parent / "benchmark" / "questions.json").read_text(encoding="utf-8"))
questions = benchmark["questions"]

pages = {}  # (source_id, page) -> (văn bản chuẩn hóa, category)
for source in manifest["sources"]:
    for page in load_pdf(ROOT / "data" / source["source_path_or_url"], source["source_id"],
                         source["source_path_or_url"], pages=source["content_pages"]):
        pages[(source["source_id"], page.page)] = (norm(page.text), source["category"])

errors = []
for q in questions:
    key = (q["gold_source_id"], q["gold_page"])
    if key not in pages:
        errors.append(f"{q['id']}: trang gold {key} không nằm trong content_pages")
        continue
    evidence = norm(q["evidence_quote"])
    if evidence not in pages[key][0]:
        errors.append(f"{q['id']}: evidence KHÔNG có ở {key}")
    # Evidence có xuất hiện ở trang khác không? (cần ghi alternative_gold nếu hợp lệ)
    elsewhere = [k for k, (text, _) in pages.items() if k != key and evidence in text]
    declared = {(a["gold_source_id"], a["gold_page"]) for a in q.get("alternative_gold", [])}
    for k in elsewhere:
        if k not in declared:
            errors.append(f"{q['id']}: evidence cũng xuất hiện ở {k} nhưng chưa khai báo alternative_gold")
    for k in declared:
        if k not in pages or evidence not in pages[k][0] and not any(
            norm(a["evidence_quote"]) in pages[k][0] for a in q["alternative_gold"]
            if (a["gold_source_id"], a["gold_page"]) == k
        ):
            errors.append(f"{q['id']}: alternative_gold {k} không chứa evidence")
    if q["filter"]:
        for field, value in q["filter"].items():
            if field != "category" or value != pages[key][1]:
                errors.append(f"{q['id']}: filter {q['filter']} không khớp category của trang gold ({pages[key][1]})")
    if len(evidence) > 220:
        errors.append(f"{q['id']}: evidence dài {len(evidence)} ký tự, nên rút ngắn")

ids = [q["id"] for q in questions]
dev = [q for q in questions if q["split"] == "dev"]
test = [q for q in questions if q["split"] == "test"]
filters = [q for q in questions if q["filter"]]
dev_pages = {(q["gold_source_id"], q["gold_page"]) for q in dev}
test_pages = {(q["gold_source_id"], q["gold_page"]) for q in test}

if len(set(ids)) != len(ids):
    errors.append("ID câu hỏi bị trùng")
if len(questions) < 20 or len(dev) < 15 or len(test) < 5:
    errors.append(f"Thiếu câu: tổng {len(questions)}, dev {len(dev)}, test {len(test)} (cần ≥20, ≥15, ≥5)")
if len(filters) < 3 or not any(q["split"] == "test" for q in filters):
    errors.append("Cần ≥3 câu có filter, trong đó ≥1 câu thuộc test")
if dev_pages & test_pages:
    errors.append(f"Trang gold trùng giữa dev và test: {sorted(dev_pages & test_pages)}")

print(f"Tổng {len(questions)} câu | dev {len(dev)} | test {len(test)} | có filter {len(filters)} "
      f"(test: {sum(q['split'] == 'test' for q in filters)})")
print("Loại câu:", {t: sum(q["type"] == t for q in questions) for t in sorted({q["type"] for q in questions})})
if errors:
    print(f"\n{len(errors)} VẤN ĐỀ:")
    for error in errors:
        print(" -", error)
    sys.exit(1)
print("Benchmark OK: mọi evidence có thật ở trang gold, split và filter đủ yêu cầu.")
