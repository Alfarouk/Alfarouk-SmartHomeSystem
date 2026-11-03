from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .commands import parse, process
from .controller import CommandError, Home


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smart Home System — local academic-project demo")
    parser.add_argument("--state-file", type=Path, help="Optional persistent simulation state")
    sub = parser.add_subparsers(dest="mode")
    sub.add_parser("console", help="Interactive text commands")
    run = sub.add_parser("command", help="Execute one text command")
    run.add_argument("text")
    run.add_argument("--code", help="Simulation control code (default2468)")
    sub.add_parser("status", help="Print simulated device state as JSON")
    serve = sub.add_parser("serve", help="Open the local dashboard")
    serve.add_argument("--port", type=int, default=8766)
    voice = sub.add_parser("voice", help="Optional offline speech input")
    voice.add_argument("--audio-file", type=Path, help="Read a WAV file instead of the microphone")
    voice.add_argument("--wake-word", default="home assistant", help="Required opening phrase")
    voice.add_argument("--speak", action="store_true", help="Read the result aloud with the tts extra")
    tts = sub.add_parser("speak", help="Optional local text-to-speech output")
    tts.add_argument("text")
    tts.add_argument("--output-audio", type=Path, help="Save speech without playing it")
    face = sub.add_parser("face-compare", help="Optional local comparison of two consented face images")
    face.add_argument("reference", type=Path)
    face.add_argument("probe", type=Path)
    face.add_argument("--models", type=Path, default=Path("models"))
    sub.add_parser("serial-loopback", help="Check serial framing without physical hardware")
    device = sub.add_parser("device", help="Add/remove a configured simulated device")
    device_modes = device.add_subparsers(dest="device_mode", required=True)
    add = device_modes.add_parser("add")
    add.add_argument("file", type=Path, help="JSON device object")
    remove = device_modes.add_parser("remove")
    remove.add_argument("device_id")
    scene = sub.add_parser("scene", help="Save/remove a configured scene")
    scene_modes = scene.add_subparsers(dest="scene_mode", required=True)
    save = scene_modes.add_parser("save")
    save.add_argument("name")
    save.add_argument("file", type=Path, help="JSON array of scene operations")
    remove_scene = scene_modes.add_parser("remove")
    remove_scene.add_argument("name")
    config = sub.add_parser("config", help="Import/export the home configuration")
    config.add_argument("config_mode", choices=["import", "export"])
    config.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode == "face-compare":
            from .face import compare
            print(json.dumps(compare(args.reference, args.probe, args.models), indent=2))
            return 0
        if args.mode == "serial-loopback":
            from .serial_link import SerialLink
            with SerialLink("loop://") as link:
                print(json.dumps(link.exchange("PING"), indent=2))
            return 0
        if args.mode == "speak":
            from .voice import speak
            speak(args.text, args.output_audio)
            return 0
        home = Home(state_file=args.state_file, code=os.getenv("SMART_HOME_CONTROL_CODE", "2468"))
        if args.mode in {"device", "scene", "config"}:
            def read_json(path: Path):
                if not path.is_file() or path.stat().st_size > 100_000:
                    raise CommandError("Use a JSON configuration file smaller than100KB.")
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except ValueError as e:
                    raise CommandError("Configuration file is not valid JSON.") from e
            if args.mode == "device":
                result = (home.add_device(read_json(args.file)) if args.device_mode == "add"
                          else home.remove_device(args.device_id))
            elif args.mode == "scene":
                result = (home.save_scene(args.name, read_json(args.file)) if args.scene_mode == "save"
                          else home.remove_scene(args.name))
            elif args.config_mode == "import":
                result = home.replace_configuration(read_json(args.file))
            else:
                args.file.write_text(json.dumps(home.data, indent=2) + "\n", encoding="utf-8")
                print(f"Simulation configuration exported to {args.file}")
                return 0
            print(json.dumps(result.to_dict(), indent=2))
            return 0 if result.ok else 2
        if args.mode == "serve":
            from .server import make_server
            with make_server(home, port=args.port) as server:
                print(f"Smart Home simulation: http://127.0.0.1:{server.server_port}", flush=True)
                print("Press Control+C to stop. No physical hardware is connected.", flush=True)
                try:
                    server.serve_forever(poll_interval=0.2)
                except KeyboardInterrupt:
                    pass
            return 0
        if args.mode == "status":
            print(json.dumps(home.snapshot(), indent=2))
            return 0
        if args.mode == "command":
            result = process(home, args.text, code=args.code)
            print(json.dumps({"result": result.to_dict(), "state": home.snapshot()}, indent=2))
            return 0 if result.ok else 2
        if args.mode == "voice":
            from .voice import command_after_wake_word, listen_once
            text = listen_once(args.audio_file)
            print(f"Recognized locally: {text}")
            command = command_after_wake_word(text, args.wake_word)
            result = process(home, command)  # Voice never supplies an unlock/disarm code implicitly.
            print(result.message)
            if args.speak:
                from .voice import speak
                speak(result.message)
            return 0 if result.ok else 2
        print("Smart Home simulation. Type help, status or exit. Demo control code:2468.")
        while True:
            try:
                text = input("You > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if text.lower() in {"exit", "quit", "stop"}:
                break
            try:
                parsed = parse(home, text)
                operations = parsed.operations
                if parsed.scene:
                    needs_code = any(s["command"] in {"unlock", "disarm"}
                                     for s in home.data["scenes"][parsed.scene])
                else:
                    needs_code = any(o.command in {"unlock", "disarm"} for o in operations)
            except CommandError:
                needs_code = False
            code = input("Control code > ") if needs_code else None
            print(process(home, text, code=code).message)
        return 0
    except (CommandError, OSError, ImportError) as e:
        print(f"Smart Home: {e}", file=sys.stderr)
        return 2
