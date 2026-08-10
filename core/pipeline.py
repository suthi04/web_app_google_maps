"""
pipeline.py
===========
ร้อยทุกขั้นตอนเข้าด้วยกัน = หัวใจของระบบ

ลำดับ (ตรงกับ flowchart รูป 3.2 ในเล่ม):
  URL --> scraper --> preprocess (คัดไทย+ทำความสะอาด)
      --> sentiment --> aspect --> keywords --> insights
      --> ประกอบเป็นผลลัพธ์ (dict) ที่พร้อมเก็บลง DB และส่งให้ dashboard

ฟังก์ชันหลัก: run_analysis(url, max_reviews) -> dict ผลลัพธ์
"""
import logging

import config
from core import scraper, preprocess, sentiment, aspect, insights, audience_insights
from core.phrases import extract, quality, canonical, synonyms, aggregate, llm_extract

# internal aspect value -> dashboard contract key
_ASPECT_KEY = {"food": "food", "service": "service", "atmosphere": "ambience"}
log = logging.getLogger(__name__)


def rule_phrase_occurrences(reviews: list, use_model: bool | None = None) -> list:
    """คืน Phrase ทุก occurrence ก่อน aggregate สำหรับ audit/evaluation

    ``reviews`` ต้องผ่าน preprocess, sentiment และ aspect แล้วเหมือน input ของ
    ``_rule_phrase_pipeline`` การแยกฟังก์ชันนี้ทำให้ตัวประเมินวัดระดับวลีจริงได้
    โดย dashboard contract เดิมไม่เปลี่ยน
    """
    collected = []
    for review_index, r in enumerate(reviews):
        try:
            for clause in r.get("clauses", []):
                clause_aspects = aspect.detect_clause_aspects(clause)
                for p in quality.filter_phrases(extract.extract(clause), clause_aspects):
                    canonical.canonicalize(p)
                    synonyms.aggregate(p)
                    if p.aspect is None:                   # not preset by earlier stage
                        a, conf = aspect.route_aspect(p, clause_aspects)
                        p.aspect, p.aspect_conf = a, conf
                    if p.aspect is None:
                        continue
                    p.aspect = _ASPECT_KEY.get(p.aspect, p.aspect)
                    p.sentiment = sentiment.classify_phrase(p, use_model=use_model)
                    p.review_index = review_index
                    collected.append(p)
        except Exception as e:                             # never let one review 500 the run
            log.warning("Skipped one review during phrase extraction: %s", e)
            continue
    return collected


def _rule_phrase_pipeline(reviews: list, use_model: bool | None = None) -> dict:
    return aggregate.build(rule_phrase_occurrences(reviews, use_model=use_model))


def _merge_keyword_contracts(primary: dict, verifier: dict) -> dict:
    """Keep Gemini discoveries while guaranteeing at least the verified rule output.

    Identical display phrases are de-duplicated by aspect/sentiment and their source
    review IDs are unioned. Counts are not added because both engines may have found
    the same occurrence.
    """
    result = {}
    aspects = list(dict.fromkeys([*(primary or {}).keys(), *(verifier or {}).keys()]))
    for aspect_name in aspects:
        result[aspect_name] = {}
        for sentiment_name in ("positive", "neutral", "negative"):
            merged = []
            positions = {}
            for source in (primary, verifier):
                for raw in ((source or {}).get(aspect_name, {}).get(sentiment_name, []) or []):
                    item = dict(raw)
                    word = " ".join(str(item.get("word") or "").casefold().split())
                    if not word:
                        continue
                    if word in positions:
                        current = merged[positions[word]]
                        ids = list(dict.fromkeys(
                            (current.get("evidence_review_ids") or [])
                            + (item.get("evidence_review_ids") or [])
                        ))
                        current["evidence_review_ids"] = ids
                        current["review_count"] = len(ids)
                        current["count"] = max(
                            int(current.get("count") or 0), int(item.get("count") or 0)
                        )
                        continue
                    item["evidence_review_ids"] = list(dict.fromkeys(
                        item.get("evidence_review_ids") or []
                    ))
                    item["review_count"] = len(item["evidence_review_ids"])
                    positions[word] = len(merged)
                    merged.append(item)
            result[aspect_name][sentiment_name] = sorted(
                merged, key=lambda item: (-int(item.get("count") or 0), item.get("word", ""))
            )
    return result


def _phrase_pipeline(
    reviews: list,
    extract_engine: str | None = None,
    use_model: bool | None = None,
):
    """Dispatch to the configured engine and report which engine ACTUALLY ran.

    Returns (contract, engine_used, narrative). engine_used is "rule" even when the LLM engine
    was selected but unavailable or its call failed (e.g. quota/429) — so the result
    label never claims an engine that didn't actually produce the phrases.
    """
    selected_engine = (
        config.get_extract_engine() if extract_engine is None else extract_engine
    )
    if selected_engine == "llm" and llm_extract.available():
        try:
            keywords, narrative = llm_extract.extract_bundle(reviews)
            verified_keywords = _rule_phrase_pipeline(reviews, use_model=use_model)
            return _merge_keyword_contracts(keywords, verified_keywords), "llm", narrative
        except Exception as e:
            log.warning("LLM phrase extraction failed; using rules: %s", e)
    return _rule_phrase_pipeline(reviews, use_model=use_model), "rule", {}


def _percentages(counts: dict, total: int) -> dict:
    """ปัดเป็นเปอร์เซ็นต์จำนวนเต็มที่ "รวมกันได้ 100 เสมอ" (largest-remainder method)

    การปัดแต่ละค่าแยกกันด้วย round() อาจให้ผลรวม 99 หรือ 101 (เช่น 33+33+33)
    วิธีนี้ปัดลงก่อนแล้วแจกเศษที่เหลือให้ค่าที่มีเศษทศนิยมมากสุด จึงรวมเป็น 100 พอดี
    เมื่อ total <= 0 (ไม่มีรีวิว) คืน 0 ทั้งหมด
    """
    if total <= 0:
        return {k: 0 for k in counts}
    exact = {k: counts[k] / total * 100 for k in counts}
    pct = {k: int(exact[k]) for k in counts}          # floor
    remainder = 100 - sum(pct.values())               # 0..2
    for k in sorted(counts, key=lambda k: exact[k] - pct[k], reverse=True)[:remainder]:
        pct[k] += 1
    return pct


def _sentiment_distribution(reviews: list) -> dict:
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for r in reviews:
        dist[r["sentiment"]] += 1
    return {
        "counts": dist,
        "total": len(reviews),
        "pct": _percentages(dist, len(reviews)),
    }


def run_analysis(
    url: str,
    max_reviews: int = None,
    use_model: bool | None = None,
    extract_engine: str | None = None,
    progress_callback=None,
) -> dict:
    def report(stage: str, progress: int) -> None:
        if progress_callback is not None:
            progress_callback(stage, progress)

    # 1) ดึงรีวิว (Apify หรือ demo)
    report("fetching_reviews", 10)
    raw = scraper.fetch_reviews(url, max_reviews)
    fetched = len(raw["reviews"])          # ที่ดึงมา (ก่อนคัดไทย) — ใช้แสดงความโปร่งใส

    # 2) คัดไทย + ทำความสะอาด + ตัดคำ
    report("preprocessing", 30)
    reviews = preprocess.filter_and_prepare(raw["reviews"])
    for index, review in enumerate(reviews, 1):
        review["review_id"] = f"R{index:03d}"

    # 3) วิเคราะห์อารมณ์
    report("sentiment", 50)
    reviews = sentiment.analyze_all(reviews, use_model=use_model)

    # 4) จัดหมวด aspect
    report("aspects", 65)
    reviews = aspect.tag_aspects(reviews)

    # 5) สรุป + สกัด keyword + insight
    distribution = _sentiment_distribution(reviews)
    aspect_summary = aspect.aspect_sentiment_summary(reviews)
    report("phrases", 78)
    requested_extract_engine = (
        config.get_extract_engine() if extract_engine is None else extract_engine
    )
    kw, engine_used, analysis_narrative = _phrase_pipeline(
        reviews, extract_engine=requested_extract_engine, use_model=use_model
    )
    report("insights", 90)
    actionable = insights.generate_insights(
        aspect_summary, kw, narrative=analysis_narrative
    )

    # 6) ประกอบผลลัพธ์
    report("finalizing", 96)
    result = {
        "store_name": raw["store_name"],
        "source_url": raw["source_url"],
        "total_reviews": len(reviews),       # ที่วิเคราะห์จริง (รีวิวไทยหลังคัดกรอง)
        "fetched_reviews": fetched,          # ที่ดึงมาทั้งหมด (รวมภาษาอื่น/ซ้ำ ที่ถูกคัดออก)
        "engine": sentiment.engine_name(use_model=use_model),
        "extract_engine": engine_used,
        "extract_engine_requested": requested_extract_engine,
        "extract_engine_fallback": (
            requested_extract_engine == "llm" and engine_used == "rule"
        ),
        "analysis_narrative": analysis_narrative,
        "distribution": distribution,        # %, counts
        "aspect_summary": aspect_summary,     # นับอารมณ์ราย aspect
        "keywords": kw,                       # keyword ราย aspect/sentiment
        "insights": actionable,               # ข้อสรุปเชิงปฏิบัติ
        "reviews": [                          # ตารางรีวิว (All)
            {
                "review_id": r["review_id"],
                "text": r["text"],
                "rating": r["rating"],
                "review_date": r["review_date"],
                "sentiment": r["sentiment"],
                "aspects": r["aspects"],
            }
            for r in reviews
        ],
    }
    return audience_insights.enrich_result(result)
