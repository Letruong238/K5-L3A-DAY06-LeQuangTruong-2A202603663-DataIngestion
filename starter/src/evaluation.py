"""Chấm bằng chứng truy xuất và giữ trace từng câu hỏi."""
import re
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Kiểm tra từng kết quả top-k có đúng nguồn/trang và chứa ĐỦ đoạn evidence không.

    Câu hỏi gồm: id, split, question, gold_source_id, gold_page, evidence_quote,
    filter (tùy chọn) và alternative_gold (tùy chọn): danh sách thêm các bằng chứng hợp lệ khác,
    mỗi phần tử có gold_source_id, gold_page, evidence_quote. Chỉ cần khớp một trong số đó.
    Hàm này KHÔNG chấm coherence hay grounding (hai tiêu chí đó chấm thủ công).
    """
    golds = [{
        "source": question["gold_source_id"],
        "page": question["gold_page"],
        "evidence": question["evidence_quote"],
    }] + [
        {"source": g["gold_source_id"], "page": g["gold_page"], "evidence": g["evidence_quote"]}
        for g in question.get("alternative_gold", [])
    ]
    for gold in golds: 
        gold["evidence"] = re.sub(r"\s+", " ", gold["evidence"]).strip().lower()

    ranked = []
    for rank, hit in enumerate(hits, start=1):
        text = re.sub(r"\s+", " ", hit["text"]).strip().lower()
        is_hit = any(
            hit["document_id"] == gold["source"]
            and hit["page"] == gold["page"]
            and gold["evidence"] in text
            for gold in golds
        )
        ranked.append({
            "rank": rank,
            "chunk_id": hit["chunk_id"],
            "document_id": hit["document_id"],
            "source": hit["source"],
            "page": hit["page"],
            "score": hit["score"],
            "text": hit["text"],
            "metadata": hit["metadata"],
            "is_hit": is_hit,
        })

    # Câu có filter: mọi kết quả top-k phải tuân thủ filter. Không có filter thì để None (N/A).
    question_filter = question.get("filter")
    filter_ok = None
    if question_filter:
        filter_ok = all(
            all(item["metadata"].get(key) == value for key, value in question_filter.items())
            for item in ranked
        )

    return {
        "question_id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "filter": question_filter,
        "gold": golds,
        "hits": ranked,
        "hit_at_1": bool(ranked) and ranked[0]["is_hit"],
        "hit_at_3": any(item["is_hit"] for item in ranked[:3]),
        "filter_ok": filter_ok,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Tổng hợp Hit@1 và Evidence Hit@3 theo chiến lược và theo dev/test (báo số tử/mẫu).

    Mỗi trace cần có thêm khóa "strategy" (do run.py thêm vào sau evaluate_query).
    """
    summary: dict[str, Any] = {}
    for trace in traces:
        group = summary.setdefault(trace["strategy"], {}).setdefault(trace["split"], {
            "questions": 0, "hit_at_1": 0, "hit_at_3": 0,
            "filter_questions": 0, "filter_ok": 0,
        })
        group["questions"] += 1
        group["hit_at_1"] += int(trace["hit_at_1"])
        group["hit_at_3"] += int(trace["hit_at_3"])
        if trace["filter_ok"] is not None:
            group["filter_questions"] += 1
            group["filter_ok"] += int(trace["filter_ok"])

    for splits in summary.values():
        for group in splits.values():
            n = group["questions"]
            group["hit_at_1_rate"] = group["hit_at_1"] / n if n else None
            group["hit_at_3_rate"] = group["hit_at_3"] / n if n else None
    return summary
