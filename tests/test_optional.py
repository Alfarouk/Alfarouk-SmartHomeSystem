from pathlib import Path
import tempfile
import unittest

from smart_home.controller import CommandError
from smart_home.face import verify_models


class OptionalBoundaryTests(unittest.TestCase):
    def test_invalid_audio_produces_readable_refusal(self):
        from smart_home.voice import listen_once
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "not-audio.wav"
            p.write_bytes(b"not audio")
            with self.assertRaises(CommandError):
                listen_once(p)

    def test_wake_phrase_is_explicit_and_not_a_substring(self):
        from smart_home.voice import command_after_wake_word
        self.assertEqual(command_after_wake_word("Home Assistant turn on lights"), "turn on lights")
        for text in ["turn on lights", "not home assistant turn on lights", "home assistant"]:
            with self.assertRaises(CommandError):
                command_after_wake_word(text)

    def test_missing_face_models_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(CommandError):
            verify_models(Path(d))

    def test_serial_loopback_when_extra_installed(self):
        try:
            import serial  # noqa: F401
        except ImportError:
            self.skipTest("Optional serial extra not installed")
        from smart_home.serial_link import SerialLink
        with SerialLink("loop://") as link:
            result = link.exchange("PING", request_id=42)
            self.assertTrue(result["ok"])
            self.assertFalse(result["physical_hardware_tested"])
            with self.assertRaises(CommandError):
                link.exchange("UNKNOWN")

    def test_remote_serial_url_is_not_accepted(self):
        from smart_home.serial_link import SerialLink
        with self.assertRaises(CommandError):
            SerialLink("socket://example.com:1234")


if __name__ == "__main__":
    unittest.main()
