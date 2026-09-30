import tempfile
import unittest
from pathlib import Path

import numpy as np

from allosaurus.audio import read_audio


class PcmAudioTest(unittest.TestCase):
    def test_reads_kspon_style_pcm(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pcm"
            samples = np.array([-32768, -1, 0, 1, 32767], dtype="<i2")
            path.write_bytes(samples.tobytes())

            audio = read_audio(path)

            self.assertEqual(audio.sample_rate, 16000)
            self.assertEqual(audio.channel_number, 1)
            self.assertEqual(audio.sample_width, 2)
            np.testing.assert_array_equal(audio.samples, samples)

    def test_header_only_does_not_load_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pcm"
            path.write_bytes(b"\x00\x00" * 1600)

            audio = read_audio(path, header_only=True)

            self.assertEqual(audio.sample_size, 1600)
            self.assertEqual(len(audio.samples), 0)


if __name__ == "__main__":
    unittest.main()
