"""Optional local voice input; text/dashboard mode does not import audio packages."""
from pathlib import Path
import json
import subprocess
import sys

from .controller import CommandError


def command_after_wake_word(text: str, wake_word: str = "home assistant") -> str:
    """Require the explicit opening phrase; never use fuzzy activation."""
    clean = " ".join(text.lower().split())
    opening = " ".join(wake_word.lower().split())
    if not opening or not clean.startswith(opening + " "):
        raise CommandError("No change made. Start the spoken command with '" + opening + "'.")
    command = clean[len(opening):].strip()
    if not command:
        raise CommandError("No command followed the wake phrase.")
    return command


def listen_once(audio_file: Path | None = None) -> str:
    try:
        import speech_recognition as sr
    except ImportError as e:
        raise CommandError("Install the voice extra: pip install '.[voice]'.") from e
    recognizer = sr.Recognizer()
    try:
        if audio_file:
            with sr.AudioFile(str(audio_file)) as source:
                audio = recognizer.record(source, duration=10)
        else:
            try:
                microphone = sr.Microphone()
            except (AttributeError, OSError) as e:
                raise CommandError("No microphone backend. Install PortAudio and '.[microphone]'.") from e
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)
        # Offline engine: audio is not sent to Google or another external service.
        return recognizer.recognize_sphinx(audio).strip()
    except sr.WaitTimeoutError as e:
        raise CommandError("No speech detected within five seconds.") from e
    except sr.UnknownValueError as e:
        raise CommandError("Speech was not understood. No device state changed.") from e
    except sr.RequestError as e:
        raise CommandError("Offline recognizer is unavailable; install the voice extra.") from e
    except (ValueError, EOFError) as e:
        raise CommandError("Cannot read this audio. Use a valid PCM WAV, AIFF or FLAC file.") from e


def speak(text: str, output_file: Path | None = None) -> None:
    """Bound native speech-driver work to a separate process and20seconds."""
    if not isinstance(text, str) or not 1 <= len(text) <= 1000:
        raise CommandError("Speech output needs1–1000characters.")
    payload = {"text": text, "output_file": str(output_file) if output_file else None}
    try:
        result = subprocess.run([sys.executable, "-m", "smart_home.tts"],
                                input=json.dumps(payload), text=True, capture_output=True, timeout=20)
    except subprocess.TimeoutExpired as e:
        raise CommandError("Local speech output timed out; device state is unchanged.") from e
    if result.returncode:
        raise CommandError("Local speech output is unavailable. Install '.[tts]' and the "
                           "platform speech backend. " + result.stderr.strip()[-300:])
    if output_file and (not output_file.is_file() or output_file.stat().st_size < 100):
        raise CommandError("The speech driver did not produce a usable audio file.")
