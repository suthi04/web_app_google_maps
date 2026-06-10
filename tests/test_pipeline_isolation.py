"""One malformed review/clause must not bring down the whole phrase pipeline."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import pipeline
from core.phrases import extract


class TestPipelineIsolation(unittest.TestCase):
    def test_one_bad_clause_does_not_crash_pipeline(self):
        good = {"clauses": [{"raw_tokens": ["อาหาร", "อร่อย"], "tokens": ["อาหาร", "อร่อย"],
                             "tokens_base": ["อาหาร", "อร่อย"], "sentiment": "positive",
                             "clean": "อาหารอร่อย"}]}
        bad = {"clauses": [{"raw_tokens": ["x"]}]}

        real_extract = extract.extract

        def boom(clause):
            if clause.get("raw_tokens") == ["x"]:
                raise RuntimeError("boom")
            return real_extract(clause)

        with mock.patch.object(extract, "extract", side_effect=boom):
            out = pipeline._phrase_pipeline([bad, good])   # must not raise
        self.assertIn("food", out)   # good review still produced output
