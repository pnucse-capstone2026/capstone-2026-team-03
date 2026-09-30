import tempfile
import unittest
from pathlib import Path

from scripts.extend_kspon_train_manifest import extend_manifests


class ExtendKsponTrainManifestTest(unittest.TestCase):
    def test_adds_only_train_and_preserves_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base"
            for split, uid in (("train", "old_train"), ("validate", "fixed_val"), ("test", "fixed_test")):
                split_dir = base / split
                split_dir.mkdir(parents=True)
                (split_dir / "wave").write_text(f"{uid} /audio/{uid}.wav\n", encoding="utf-8")
                (split_dir / "text").write_text(f"{uid} k a\n", encoding="utf-8")
            (base / "validate" / "feat.ark").write_bytes(b"ark")
            for name in ("feat.scp", "shape", "token"):
                (base / "validate" / name).write_text("x\n", encoding="utf-8")

            audio_root = root / "KsponSpeech_02"
            (audio_root / "part").mkdir(parents=True)
            (audio_root / "part" / "new.pcm").write_bytes(b"\x00\x00")
            labels = root / "labels" / "KsponSpeech_02" / "part"
            labels.mkdir(parents=True)
            (labels / "new.txt").write_text("k a\n", encoding="utf-8")
            inventory = root / "inventory.txt"
            inventory.write_text("k\na\n", encoding="utf-8")
            output = root / "expanded"

            summary = extend_manifests(base, [audio_root], root / "labels", output, inventory)

            self.assertEqual(summary["counts"]["train"], 2)
            self.assertEqual(summary["counts"]["validate"], 1)
            self.assertEqual((output / "validate" / "wave").read_text(), (base / "validate" / "wave").read_text())
            self.assertTrue((output / "validate" / "feat.ark").is_symlink())
            self.assertIn("KsponSpeech_02__part__new", (output / "train" / "wave").read_text())

    def test_adds_processed_wav_with_adjacent_ipa_label(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base"
            for split, uid in (("train", "old_train"), ("validate", "fixed_val"), ("test", "fixed_test")):
                split_dir = base / split
                split_dir.mkdir(parents=True)
                (split_dir / "wave").write_text(f"{uid} /audio/{uid}.wav\n", encoding="utf-8")
                (split_dir / "text").write_text(f"{uid} k a\n", encoding="utf-8")

            paired_root = root / "KsponSpeech_02"
            paired_root.mkdir()
            (paired_root / "new.wav").write_bytes(b"RIFF")
            (paired_root / "new.txt").write_text("k a\n", encoding="utf-8")
            inventory = root / "inventory.txt"
            inventory.write_text("k\na\n", encoding="utf-8")
            output = root / "expanded"

            summary = extend_manifests(
                base,
                [],
                root / "unused-labels",
                output,
                inventory,
                paired_roots=[paired_root],
            )

            self.assertEqual(summary["counts"]["train"], 2)
            wave = (output / "train" / "wave").read_text(encoding="utf-8")
            self.assertIn("KsponSpeech_02__new", wave)
            self.assertIn(str((paired_root / "new.wav").resolve()), wave)


if __name__ == "__main__":
    unittest.main()
