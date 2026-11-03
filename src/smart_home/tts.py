"""Isolated optional speech-output worker; invoked by smart_home.voice.speak."""
import json
import sys


def main() -> int:
    try:
        import pyttsx3
        payload = json.loads(sys.stdin.read(10000))
        engine = pyttsx3.init()
        try:
            engine.setProperty("rate", 150)
            if payload["output_file"]:
                engine.save_to_file(payload["text"], payload["output_file"])
            else:
                engine.say(payload["text"])
            engine.runAndWait()
        finally:
            engine.stop()
        return 0
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
