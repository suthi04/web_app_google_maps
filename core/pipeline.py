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
import config
from core import scraper, preprocess, sentiment, aspect, insights
from core.phrases import extract, quality, canonical, synonyms, aggregate, llm_extract

# internal aspect value -> dashboard contract key
_ASPECT_KEY = {"food": "food", "service": "service", "atmosphere": "ambience"}


def _rule_phrase_pipeline(reviews: list) -> dict:
    collected = []
    for r in reviews:
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
                    p.sentiment = sentiment.classify_phrase(p)
                    collected.append(p)
        except Exception as e:                             # never let one review 500 the run
            print(f"[phrases] skipped a review due to: {e}")
            continue
    return aggregate.build(collected)


def _phrase_pipeline(reviews: list):
    """Dispatch to the configured engine and report which engine ACTUALLY ran.

    Returns (contract, engine_used). engine_used is "rule" even when the LLM engine
    was selected but unavailable or its call failed (e.g. quota/429) — so the result
    label never claims an engine that didn't actually produce the phrases.
    """
    if config.get_extract_engine() == "llm" and llm_extract.available():
        try:
            return llm_extract.extract_all(reviews), "llm"
        except Exception as e:
            print(f"[phrases] LLM engine failed, falling back to rule-based: {e}")
    return _rule_phrase_pipeline(reviews), "rule"


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


def run_analysis(url: str, max_reviews: int = None) -> dict:
    # 1) ดึงรีวิว (Apify หรือ demo)
    raw = scraper.fetch_reviews(url, max_reviews)
    fetched = len(raw["reviews"])          # ที่ดึงมา (ก่อนคัดไทย) — ใช้แสดงความโปร่งใส

    # 2) คัดไทย + ทำความสะอาด + ตัดคำ
    reviews = preprocess.filter_and_prepare(raw["reviews"])

    # 3) วิเคราะห์อารมณ์
    reviews = sentiment.analyze_all(reviews)

    # 4) จัดหมวด aspect
    reviews = aspect.tag_aspects(reviews)

    # 5) สรุป + สกัด keyword + insight
    distribution = _sentiment_distribution(reviews)
    aspect_summary = aspect.aspect_sentiment_summary(reviews)
    kw, extract_engine = _phrase_pipeline(reviews)   # engine_used = ตัวที่ทำงานจริง
    actionable = insights.generate_insights(aspect_summary, kw)

    # 6) ประกอบผลลัพธ์
    return {
        "store_name": raw["store_name"],
        "source_url": raw["source_url"],
        "total_reviews": len(reviews),       # ที่วิเคราะห์จริง (รีวิวไทยหลังคัดกรอง)
        "fetched_reviews": fetched,          # ที่ดึงมาทั้งหมด (รวมภาษาอื่น/ซ้ำ ที่ถูกคัดออก)
        "engine": sentiment.engine_name(),
        "extract_engine": extract_engine,
        "distribution": distribution,        # %, counts
        "aspect_summary": aspect_summary,     # นับอารมณ์ราย aspect
        "keywords": kw,                       # keyword ราย aspect/sentiment
        "insights": actionable,               # ข้อสรุปเชิงปฏิบัติ
        "reviews": [                          # ตารางรีวิว (All)
            {
                "text": r["text"],
                "rating": r["rating"],
                "review_date": r["review_date"],
                "sentiment": r["sentiment"],
                "aspects": r["aspects"],
            }
            for r in reviews
        ],
    }
