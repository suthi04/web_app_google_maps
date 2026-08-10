import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import aspect, lexicon, sentiment
from core.phrases import canonical, extract, quality


def prepared_phrases(raw_tokens, cached_sentiment="neutral"):
    clause = {
        "raw_tokens": raw_tokens,
        "tokens": raw_tokens,
        "clean": "".join(raw_tokens),
        "sentiment": cached_sentiment,
    }
    clause_aspects = aspect.detect_clause_aspects(clause)
    phrases = quality.filter_phrases(extract.extract(clause), clause_aspects)
    for phrase in phrases:
        canonical.canonicalize(phrase)
        if phrase.aspect is None:
            phrase.aspect, phrase.aspect_conf = aspect.route_aspect(phrase, clause_aspects)
    return phrases


class TestContemporaryThaiLexicon(unittest.TestCase):
    def test_clear_slang_has_polarity(self):
        for word in ("เริ่ด", "เริส", "ปัง", "จึ้ง", "นัว", "ทำถึง"):
            self.assertEqual(sentiment._predict_lexicon([word]), "positive", word)
        for word in ("บ้ง", "ตุ้บ", "พัง", "เฟล", "แป้ก"):
            self.assertEqual(sentiment._predict_lexicon([word]), "negative", word)

    def test_ambiguous_slang_is_not_forced_to_a_polarity(self):
        for word in lexicon.AMBIGUOUS_SLANG:
            self.assertNotIn(word, lexicon.SENTIMENT_WORDS["positive"])
            self.assertNotIn(word, lexicon.SENTIMENT_WORDS["negative"])
        self.assertEqual(sentiment._predict_lexicon(["จอด", "รถ"]), "neutral")
        self.assertEqual(sentiment._predict_lexicon(["ขิต"]), "neutral")

    def test_food_slang_routes_to_food_and_uses_plain_display(self):
        phrases = prepared_phrases(["รสชาติ", "นัว", "มาก"])
        phrase = next(p for p in phrases if "กลมกล่อม" in p.display)
        self.assertEqual(phrase.aspect, "food")
        self.assertEqual(phrase.canonical, "รสชาติกลมกล่อม")
        self.assertEqual(phrase.display, "รสชาติกลมกล่อมมาก")

    def test_positive_slang_is_normalized_for_customer(self):
        phrases = prepared_phrases(["บริการ", "เริ่ด", "มาก"])
        phrase = next(p for p in phrases if p.aspect == "service")
        self.assertEqual(phrase.canonical, "บริการดี")
        self.assertEqual(phrase.display, "บริการดีมาก")

    def test_negative_slang_is_normalized_for_customer(self):
        phrases = prepared_phrases(["อาหาร", "บ้ง"])
        phrase = next(p for p in phrases if p.aspect == "food")
        self.assertEqual(phrase.canonical, "อาหารน่าผิดหวัง")
        self.assertEqual(phrase.display, "อาหารน่าผิดหวัง")

    def test_food_praise_mwe_is_readable_and_positive(self):
        phrases = prepared_phrases(["อร่อย", "แบบ", "ตะโกน"])
        phrase = next(p for p in phrases if p.pattern == "idiom")
        self.assertEqual(phrase.aspect, "food")
        self.assertEqual(phrase.display, "อาหารอร่อยมาก")
        self.assertEqual(sentiment.classify_phrase(phrase, use_model=False), "positive")

    def test_mwe_does_not_leak_into_preceding_descriptor(self):
        phrases = prepared_phrases(["อร่อย", "มาก", "โคตร", "อร่อย"])
        self.assertEqual(
            [p.display for p in phrases],
            ["อาหารอร่อยมาก", "อาหารอร่อยมาก"],
        )
        self.assertNotIn("อร่อยมากอร่อยมาก", [p.display for p in phrases])

    def test_repeated_praise_is_collapsed_for_readability(self):
        phrases = prepared_phrases(["อร่อย", "มาก", "เริ่ด", "เริ่ด", "เริ่ด"])
        phrase = phrases[0]
        self.assertEqual(phrase.canonical, "อร่อย")
        self.assertEqual(phrase.display, "อร่อยมาก")

    def test_plain_negative_word_uses_natural_customer_wording(self):
        phrases = prepared_phrases(["อาหาร", "ผิดหวัง", "มาก"])
        phrase = phrases[0]
        self.assertEqual(phrase.canonical, "อาหารน่าผิดหวัง")
        self.assertEqual(phrase.display, "อาหารน่าผิดหวังมาก")

    def test_generic_slang_mwe_uses_unambiguous_clause_aspect(self):
        phrases = prepared_phrases(["บริการ", "ช็อต", "ฟี", "ล"])
        phrase = next(p for p in phrases if p.pattern == "idiom")
        self.assertEqual(phrase.aspect, "service")
        self.assertEqual(phrase.display, "ทำให้เสียความรู้สึก")
        self.assertEqual(sentiment.classify_phrase(phrase, use_model=False), "negative")

    def test_negated_expectation_phrase_keeps_positive_meaning(self):
        phrases = prepared_phrases(["ร้าน", "ไม่", "จก", "ตา"])
        phrase = next(p for p in phrases if p.pattern == "idiom")
        self.assertEqual(phrase.display, "ตรงกับที่คาดหวัง")
        self.assertEqual(sentiment.classify_phrase(phrase, use_model=False), "positive")

    def test_review_sentiment_reads_multi_token_phrase_before_stopword_loss(self):
        self.assertEqual(
            sentiment._predict_lexicon(["เต็ม", "สิบ", "หัก"], "เต็มสิบไม่หัก"),
            "positive",
        )
        self.assertEqual(
            sentiment._predict_lexicon(["จก", "ตา"], "ร้านไม่จกตา"),
            "positive",
        )
        self.assertEqual(
            sentiment._predict_lexicon(["จก", "ตา"], "ร้านจกตา"),
            "negative",
        )


if __name__ == "__main__":
    unittest.main()
