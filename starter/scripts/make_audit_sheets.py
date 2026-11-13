"""Tạo phiếu chấm thủ công (CSV) từ chunk và trace. Cột điểm/nhãn để TRỐNG cho người chấm điền.

Chạy từ thư mục starter/:  python scripts/make_audit_sheets.py
- audit_coherence.csv : 10 vị trí nội dung cố định (không phụ thuộc điểm số), chấm 0/1/2.
- audit_metadata.csv  : 5 câu test x top-3 x A/B/C, kiểm tra source/page/category với PDF.
- audit_grounding.csv : 5 câu test x A/B/C, chấm 0/1/2.
Hai phiếu sau chỉ tạo khi results/traces.jsonl đã có câu test.
"""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size  # noqa: E402
from src.ingestion import load_pdf  # noqa: E402

RESULTS = ROOT / "results"
manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
pages = []
for source in manifest["sources"]:
    pages += load_pdf(ROOT / "data" / source["source_path_or_url"], source["source_id"],
                      source["source_path_or_url"], pages=source["content_pages"],
                      metadata={"category": source["category"], "language": source["language"]})
pages.sort(key=lambda p: (p.document_id, p.page))

# ---- 1. Coherence: 10 vị trí cố định, chọn trước khi xem bất kỳ điểm nào ----
# Quy tắc: trang thứ i*N//10 (i = 0..9) trong danh sách trang đã sắp xếp;
# vị trí = đoạn văn chứa điểm giữa trang; neo = 30 ký tự đầu của đoạn đó.
chunks = {
    "A": [c for p in pages for c in fixed_size(p, 500, 50)],
    "B": [c for p in pages for c in by_paragraph(p, 800)],
}
rows = []
for i in range(10):
    page = pages[i * len(pages) // 10]
    middle, offset, anchor = len(page.text) // 2, 0, ""
    for paragraph in page.text.split("\n\n"):
        if offset <= middle < offset + len(paragraph):
            anchor = paragraph[:30]
            break
        offset += len(paragraph) + 2
    for name in ("A", "B"):
        for chunk in chunks[name]:
            if chunk.document_id == page.document_id and chunk.page == page.page and anchor in chunk.text:
                rows.append({
                    "position": f"P{i + 1:02d}", "source_id": page.document_id, "page": page.page,
                    "anchor_text": anchor, "strategy": name, "chunk_id": chunk.chunk_id,
                    "chunk_text": chunk.text, "coherence_0_1_2": "", "reason": "",
                })
with open(RESULTS / "audit_coherence.csv", "w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f"audit_coherence.csv: {len(rows)} dòng cần chấm (C dùng chunk của B nên không chấm riêng)")

# ---- 2 & 3. Metadata và grounding cho các câu TEST (cần trace) ----
trace_path = RESULTS / "traces.jsonl"
traces = [json.loads(line) for line in open(trace_path, encoding="utf-8")] if trace_path.exists() else []
test_traces = [t for t in traces if t["split"] == "test"]
if not test_traces:
    print("Chưa có trace của tập test: bỏ qua audit_metadata.csv và audit_grounding.csv "
          "(chạy python -m src.run sau khi chốt câu hỏi).")
    sys.exit(0)

questions = {q["id"]: q for q in json.loads(
    (ROOT.parent / "benchmark" / "questions.json").read_text(encoding="utf-8"))["questions"]}

meta_rows, ground_rows = [], []
for trace in test_traces:
    question = questions[trace["question_id"]]
    for hit in trace["hits"]:
        meta_rows.append({
            "strategy": trace["strategy"], "question_id": trace["question_id"], "rank": hit["rank"],
            "chunk_id": hit["chunk_id"], "meta_source": hit["source"],
            "meta_page": hit["page"], "meta_category": hit["metadata"].get("category"),
            "filter_required": json.dumps(trace["filter"], ensure_ascii=False) if trace["filter"] else "",
            "text_preview": hit["text"][:120].replace("\n", " "),
            "source_ok": "", "page_ok": "", "category_ok": "", "all_ok": "", "note": "",
        })
    ground_rows.append({
        "strategy": trace["strategy"], "question_id": trace["question_id"],
        "question": question["question"], "expected_answer": question["expected_answer"],
        "gold_page": question["gold_page"],
        "top3": "\n---\n".join(
            f"[#{h['rank']} p{h['page']} {h['chunk_id']}] {h['text']}" for h in trace["hits"]),
        "grounding_0_1_2": "", "reason": "",
    })
for name, data in (("audit_metadata.csv", meta_rows), ("audit_grounding.csv", ground_rows)):
    with open(RESULTS / name, "w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    print(f"{name}: {len(data)} dòng cần chấm")
