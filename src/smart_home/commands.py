"""Small deterministic grammar: uncertain language never changes device state."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
import re
from typing import Any

from .controller import CommandError, Home, Operation, Result


EXAMPLES = ["turn on the lights", "dim Main Light to 30", "lock Front Door",
            "unlock Front Door", "open Window Curtain", "set Ceiling Fan speed to 40",
            "arm the alarm", "disarm the alarm", "activate scene movie time", "status"]


@dataclass(frozen=True)
class Parsed:
    operations: tuple[Operation, ...] = ()
    scene: str | None = None
    system: str | None = None
    query: str | None = None


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("don't", "do not")
    text = re.sub(r"[^a-z0-9_%\s]", " ", text)
    text = re.sub(r"\b(?:please|the|a|an)\b", " ", text)
    return " ".join(text.split())


def _targets(home: Home, raw: str, allowed: set[str]) -> list[dict[str, Any]]:
    text = normalize(raw)
    data = home.snapshot()["devices"]
    room = None
    if " in " in text:
        text, room = text.rsplit(" in ", 1)
    # Names and ids resolve before generic aliases; never select an arbitrary first match.
    direct = [d for d in data if text in {normalize(d["name"]), d["id"]}
              and (room is None or normalize(d["room"]) == room)]
    if direct:
        if len(direct) != 1 or direct[0]["type"] not in allowed:
            raise CommandError("That device name is ambiguous or does not support this command.")
        return direct
    aliases = {"lights": "light", "light": "light", "bulb": "light", "bulbs": "light",
               "lamp": "light", "lamps": "light", "doors": "door", "door": "door",
               "entrance": "door", "curtains": "curtain", "curtain": "curtain",
               "fans": "fan", "fan": "fan", "bin": "bin", "trash bin": "bin",
               "alarm": "alarm", "alarm system": "alarm", "security system": "alarm"}
    kind = aliases.get(text.removeprefix("all "))
    if kind not in allowed:
        raise CommandError("Name the device or device type, such as Main Light or curtains.")
    matches = [d for d in data if d["type"] == kind and
               (room is None or normalize(d["room"]) == room)]
    if not matches:
        raise CommandError("No matching device exists in that room.")
    return matches


def parse(home: Home, raw: str) -> Parsed:
    if not isinstance(raw, str) or not 1 <= len(raw.strip()) <= 300:
        raise CommandError("Enter a command of 1–300 characters.")
    text = normalize(raw)
    if re.search(r"\b(?:not|never|unless|except|maybe|if)\b", text):
        raise CommandError("No change made. Use one direct command without a condition or negation.")
    if re.search(r"\b(?:and|then|or)\b", text):
        raise CommandError("Use one command at a time, or run a named scene.")
    if text in {"help", "h", "commands", "show commands", "show help", "options", "menu",
                "what can you do", "what are commands"} or raw.strip() == "?":
        return Parsed(system="help")
    if text in {"status", "show status", "system status"}:
        return Parsed(system="status")
    status = re.fullmatch(r"(?:show )?status(?: of)? (.+)", text)
    if status:
        return Parsed(system="status", query=status[1])
    if text in {"exit", "quit", "stop"}:
        return Parsed(system="exit")
    scene = re.fullmatch(r"(?:activate|run) scene (.+)", text)
    if scene:
        name = scene[1].replace(" ", "_")
        if name not in home.snapshot()["scenes"]:
            raise CommandError("That scene does not exist.")
        return Parsed(scene=name)
    quick = {
        "lights on": ("turn_on", "lights"), "light on": ("turn_on", "lights"),
        "lights on please": ("turn_on", "lights"), "illuminate room": ("turn_on", "lights"),
        "make it brighter": ("turn_on", "lights"), "brighten up kitchen": ("turn_on", "lights in kitchen"),
        "lights off": ("turn_off", "lights"), "light off": ("turn_off", "lights"),
        "darken room": ("turn_off", "lights"), "make it darker": ("turn_off", "lights"),
        "kill lights": ("turn_off", "lights"), "lock": ("lock", "doors"),
        "unlock": ("unlock", "doors"), "arm": ("arm", "alarm"),
        "disarm": ("disarm", "alarm"), "enable protection": ("arm", "alarm"),
        "disable protection": ("disarm", "alarm"), "arm security": ("arm", "alarm"),
        "disarm security": ("disarm", "alarm"), "set alarm": ("arm", "alarm"),
        "unset alarm": ("disarm", "alarm"),
    }
    if text in {"activate security", "disable security", "deactivate security"}:
        raise CommandError("Say 'lock doors', 'unlock doors', 'arm alarm' or 'disarm alarm'.")
    if text in quick:
        cmd, target = quick[text]
        allowed = {"arm": {"alarm"}, "disarm": {"alarm"}, "lock": {"door"},
                   "unlock": {"door"}}.get(cmd, {"light"})
        return Parsed(tuple(Operation(d["id"], cmd) for d in _targets(home, target, allowed)))
    numeric = re.fullmatch(r"(?:dim (.+?)|set (.+?) (brightness|speed|position)) to (-?\d+)(?:%| percent)?", text)
    if numeric:
        target = numeric[1] or numeric[2]
        attribute = "brightness" if numeric[1] else numeric[3]
        kind, cmd = {"brightness": ("light", "dim"), "speed": ("fan", "set_speed"),
                     "position": ("curtain", "set_position")}[attribute]
        return Parsed(tuple(Operation(d["id"], cmd, int(numeric[4]))
                            for d in _targets(home, target, {kind})))
    color = re.fullmatch(r"(?:change|set) (.+?) color to ([a-z ]+)", text)
    if color:
        return Parsed(tuple(Operation(d["id"], "change_color", color[2])
                            for d in _targets(home, color[1], {"light"})))
    verbs = [
        (r"(?:turn on|switch on|activate|enable) (.+)", "turn_on", {"light", "fan"}),
        (r"(?:turn off|turn of|switch off|deactivate|disable) (.+)", "turn_off", {"light", "fan"}),
        (r"(?:unlock|unsecure) (.+)", "unlock", {"door"}),
        (r"(?:lock|secure) (.+)", "lock", {"door"}),
        (r"open (.+)", "open", {"door", "curtain", "bin"}),
        (r"close (.+)", "close", {"door", "curtain", "bin"}),
        (r"(?:arm|activate|enable|turn on) (alarm|alarm system|security system)", "arm", {"alarm"}),
        (r"(?:disarm|deactivate|disable|turn off) (alarm|alarm system|security system)", "disarm", {"alarm"}),
    ]
    # Exact security phrases are checked first; generic verbs cannot steal them.
    for pattern, cmd, allowed in verbs[-2:] + verbs[:-2]:
        match = re.fullmatch(pattern, text)
        if match:
            return Parsed(tuple(Operation(d["id"], cmd) for d in _targets(home, match[1], allowed)))
    suggestion = get_close_matches(text, EXAMPLES, n=1, cutoff=0.55)
    message = "No change made. Try a command from the examples."
    if suggestion:
        message += f" Did you mean '{suggestion[0]}'?"
    raise CommandError(message)


def process(home: Home, text: str, *, code: str | None = None) -> Result:
    try:
        command = parse(home, text)
        if command.system == "help":
            return Result(True, "Examples: " + "; ".join(EXAMPLES))
        if command.system == "status":
            state = home.snapshot()
            if command.query:
                selected = [d for d in state["devices"] if command.query in
                            {normalize(d["id"]), normalize(d["name"]), normalize(d["room"])}]
                if not selected:
                    return Result(False, "No matching device or room exists.")
                return Result(True, "; ".join(d["name"] + ": " + d["state"] +
                              ((", locked" if d["locked"] else ", unlocked")
                               if d["type"] == "door" else "") for d in selected))
            return Result(True, f"{len(state['devices'])} simulated devices in "
                          f"{len({d['room'] for d in state['devices']})} rooms.")
        if command.system == "exit":
            return Result(True, "Goodbye. No device state changed.")
        if command.scene:
            return home.scene(command.scene, code=code)
        return home.execute(list(command.operations), code=code)
    except CommandError as e:
        return Result(False, str(e))
