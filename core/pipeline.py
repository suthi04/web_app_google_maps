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
from core import scraper, preprocess, sentiment, aspect, keywords, insights
from core.phrases import extract, quality, canonical, synonyms, aggregate

# internal aspect value -> dashboard contract key
_ASPECT_KEY = {"food": "food", "service": "service", "atmosphere": "ambience"}


def _phrase_pipeline(reviews: list) -> dict:
    collected = []
    for r in reviews:
        for clause in r.get("clauses", []):
            clause_aspects = aspect.detect_clause_aspects(clause)
            for p in quality.filter_phrases(extract.extract(clause), clause_aspects):
                canonical.canonicalize(p)
                synonyms.aggregate(p)
                if p.aspect is None:                       # not preset by earlier stage
                    a, conf = aspect.route_aspect(p, clause_aspects)
                    p.aspect, p.aspect_conf = a, conf
                if p.aspect is None:
                    continue
                p.aspect = _ASPECT_KEY.get(p.aspect, p.aspect)
                p.sentiment = sentiment.classify_phrase(p)
                collected.append(p)
    return aggregate.build(collected)


def _sentiment_distribution(reviews: list) -> dict:
    dist = {"positive": 0, "neutral": 0, "negative": 0}
    for r in reviews:
        dist[r["sentiment"]] += 1
    total = len(reviews) or 1
    return {
        "counts": dist,
        "total": len(reviews),
        "pct": {
            "positive": round(dist["positive"] / total * 100),
            "neutral": round(dist["neutral"] / total * 100),
            "negative": round(dist["negative"] / total * 100),
        },
    }


def run_analysis(url: str, max_reviews: int = None) -> dict:
    # 1) ดึงรีวิว (Apify หรือ demo)
    raw = scraper.fetch_reviews(url, max_reviews)

    # 2) คัดไทย + ทำความสะอาด + ตัดคำ
    reviews = preprocess.filter_and_prepare(raw["reviews"])

    # 3) วิเคราะห์อารมณ์
    reviews = sentiment.analyze_all(reviews)

    # 4) จัดหมวด aspect
    reviews = aspect.tag_aspects(reviews)

    # 5) สรุป + สกัด keyword + insight
    distribution = _sentiment_distribution(reviews)
    aspect_summary = aspect.aspect_sentiment_summary(reviews)
    kw = _phrase_pipeline(reviews)
    topics = keywords.extract_topics(reviews)          # "ลูกค้าพูดถึงบ่อย" (แยกจาก insight)
    actionable = insights.generate_insights(aspect_summary, kw)

    # 6) ประกอบผลลัพธ์
    return {
        "store_name": raw["store_name"],
        "source_url": raw["source_url"],
        "total_reviews": len(reviews),
        "engine": sentiment.engine_name(),
        "distribution": distribution,        # %, counts
        "aspect_summary": aspect_summary,     # นับอารมณ์ราย aspect
        "keywords": kw,                       # keyword ราย aspect/sentiment
        "topics": topics,                     # หัวข้อที่พูดถึงบ่อย (สำรวจเท่านั้น)
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
