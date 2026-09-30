from django.test import SimpleTestCase

from pronunciation.services.alignment import pronunciation_score_with_variants
from pronunciation.services.sentence_ipa import build_sentence_ipa


class IpaVariantTests(SimpleTestCase):
    def test_build_sentence_ipa_includes_lenient_variants_for_haetseumnida(self):
        data = build_sentence_ipa("했습니다")
        variant_ipas = {tuple(variant["ipa"]) for variant in data["cached_ipa_variants"]}

        self.assertIn(
            tuple(["h", "e", "t̚", "s͈", "ɯ", "m", "n", "i", "t", "a"]),
            variant_ipas,
        )
        self.assertIn(tuple(["h", "e", "s͈", "ɯ", "m", "n", "i", "t", "a"]), variant_ipas)
        self.assertIn(
            tuple(["h", "e", "t̚", "s", "ɯ", "p̚", "n", "i", "t", "a"]),
            variant_ipas,
        )
        self.assertIn(
            tuple(["h", "e", "t̚", "s", "ɯ", "p̚", "m", "i", "t", "a"]),
            variant_ipas,
        )

    def test_pronunciation_score_with_variants_uses_best_target(self):
        standard = ["h", "e", "t̚", "s͈", "ɯ", "m", "n", "i", "t", "a"]
        lenient = ["h", "e", "s͈", "ɯ", "m", "n", "i", "t", "a"]

        score, _alignment, matched = pronunciation_score_with_variants(
            [
                {"label": "standard", "ipa": standard},
                {"label": "weak_coda_before_tense", "ipa": lenient},
            ],
            lenient,
        )

        self.assertEqual(score, 100)
        self.assertEqual(matched["label"], "weak_coda_before_tense")
        self.assertEqual(matched["ipa"], lenient)
