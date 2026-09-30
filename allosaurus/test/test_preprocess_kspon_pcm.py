import unittest

from scripts.preprocess_kspon_pcm import normalize_transcript, pronunciation_to_ipa


class PreprocessKsponPcmTest(unittest.TestCase):
    def test_normalizes_kspon_annotations_and_uses_spoken_alternative(self):
        source = "o/ (s6)/(에스 식스)에 b/ 추울+ 추울 때 가자.*"
        self.assertEqual(normalize_transcript(source), "에스 식스에 추울 추울 때 가자")

    def test_spells_ascii_letters_as_korean_letter_names(self):
        self.assertEqual(
            normalize_transcript("kfc랑 SKT 할인"),
            "케이 에프 씨 랑 에스 케이 티 할인",
        )

    def test_converts_hangul_pronunciation_to_project_inventory(self):
        phones = pronunciation_to_ipa("시작 꽈")
        self.assertEqual(phones, ["ɕ", "i", "tɕ", "a", "k̚", "k͈", "w", "a"])


if __name__ == "__main__":
    unittest.main()
