from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardAudioProbeTest(unittest.TestCase):
    def test_board_audio_probe_checks_builtin_codec_and_mic(self) -> None:
        text = (ROOT / "tools" / "board_audio_probe.sh").read_text(encoding="utf-8")

        self.assertTrue(text.startswith("#!/bin/sh"))
        self.assertIn("rockchipnau8822", text)
        self.assertIn("arecord -D hw:rockchipnau8822,0", text)
        self.assertIn("board_mic_probe.wav", text)
        self.assertIn("/dev/snd/pcmC1D0c", text)
        self.assertIn("Audio probe completed.", text)

    def test_board_health_status_reports_audio_fields(self) -> None:
        text = (ROOT / "tools" / "board_health_status.sh").read_text(encoding="utf-8")

        self.assertIn('"audio"', text)
        self.assertIn('"audio_capture"', text)
        self.assertIn('"audio_playback"', text)
        self.assertIn("arecord -l", text)
        self.assertIn("aplay -l", text)

    def test_board_ops_runs_audio_probe(self) -> None:
        text = (ROOT / "tools" / "board_ops.sh").read_text(encoding="utf-8")

        self.assertIn("Board audio probe", text)
        self.assertIn("tools/board_audio_probe.sh", text)


if __name__ == "__main__":
    unittest.main()
