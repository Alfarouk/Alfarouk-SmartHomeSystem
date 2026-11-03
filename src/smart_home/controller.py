"""One validated state machine for the CLI, dashboard and optional adapters."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import uuid
from typing import Any, Callable


class CommandError(ValueError):
    """An expected, user-readable command or configuration rejection."""


@dataclass(frozen=True)
class Operation:
    device_id: str
    command: str
    value: int | str | None = None


@dataclass(frozen=True)
class Result:
    ok: bool
    message: str
    changed: tuple[str, ...] = ()
    mode: str = "simulation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


KINDS = {"light", "door", "curtain", "fan", "bin", "alarm"}
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
OPERATIONS = {
    "light": {"turn_on", "turn_off", "dim", "change_color"},
    "door": {"open", "close", "lock", "unlock"},
    "curtain": {"open", "close", "set_position"},
    "fan": {"turn_on", "turn_off", "set_speed"},
    "bin": {"open", "close"},
    "alarm": {"arm", "disarm"},
}


def percentage(value: Any, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 100:
        raise CommandError(f"{label} must be a whole number from 0 to 100.")
    return value


def validate_document(raw: Any) -> dict[str, Any]:
    """Reject malformed state instead of silently replacing it with defaults."""
    if (not isinstance(raw, dict) or set(raw) - {"name", "devices", "scenes"}
            or not isinstance(raw.get("name"), str)):
        raise CommandError("Home configuration needs a name and a device list.")
    if not 1 <= len(raw["name"]) <= 120:
        raise CommandError("Home name must contain 1–120 characters.")
    devices = raw.get("devices")
    if not isinstance(devices, list) or not 1 <= len(devices) <= 100:
        raise CommandError("Home configuration needs 1–100 devices.")
    seen = set()
    for d in devices:
        if not isinstance(d, dict) or not IDENTIFIER.fullmatch(str(d.get("id", ""))):
            raise CommandError("Every device needs a unique lowercase id.")
        if d["id"] in seen:
            raise CommandError(f"Duplicate device id: {d['id']}.")
        seen.add(d["id"])
        if d.get("type") not in KINDS:
            raise CommandError(f"Unknown device type: {d.get('type')}.")
        if set(d) - {"id", "name", "room", "type", "state", "brightness", "color",
                     "position", "speed", "locked", "auto_close_at"}:
            raise CommandError("Device configuration has an unknown field.")
        if any(not isinstance(d.get(k), str) or not 1 <= len(d[k]) <= 80
               for k in ("name", "room")):
            raise CommandError("Device names and rooms need 1–80 characters.")
        allowed = {"light": {"on", "off"}, "fan": {"on", "off"},
                   "door": {"open", "closed"}, "bin": {"open", "closed"},
                   "curtain": {"open", "closed"}, "alarm": {"armed", "disarmed"}}
        if d.get("state") not in allowed[d["type"]]:
            raise CommandError(f"Invalid state for {d['name']}.")
        for key in ("brightness", "position", "speed"):
            if key in d:
                percentage(d[key], key.capitalize())
        if d["type"] == "light":
            if "brightness" not in d or not isinstance(d.get("color"), str):
                raise CommandError("Lights need brightness and color.")
        if d["type"] == "fan" and "speed" not in d:
            raise CommandError("Fans need speed.")
        if d["type"] == "curtain" and "position" not in d:
            raise CommandError("Curtains need position.")
        if d["type"] == "door":
            if type(d.get("locked")) is not bool or (d["state"] == "open" and d["locked"]):
                raise CommandError("A door needs a valid lock state and cannot be locked open.")
        if "auto_close_at" in d:
            t = d["auto_close_at"]
            if (type(t) not in (int, float) or not math.isfinite(t)
                    or d["type"] not in {"door", "bin"} or d["state"] != "open"):
                raise CommandError("Invalid auto-close deadline.")
    scenes = raw.get("scenes", {})
    if not isinstance(scenes, dict) or len(scenes) > 50:
        raise CommandError("Scenes must be a named mapping of at most 50 scenes.")
    for name, steps in scenes.items():
        if (not isinstance(name, str) or not IDENTIFIER.fullmatch(name)
                or not isinstance(steps, list) or not 1 <= len(steps) <= 100):
            raise CommandError("Every scene needs a valid name and 1–100 operations.")
        for step in steps:
            if not isinstance(step, dict) or set(step) - {"device_id", "command", "value"}:
                raise CommandError("Invalid scene operation.")
            if step.get("device_id") not in seen or not isinstance(step.get("command"), str):
                raise CommandError("A scene refers to a missing device or command.")
            device = next(d for d in devices if d["id"] == step["device_id"])
            if step["command"] not in OPERATIONS[device["type"]]:
                raise CommandError("A scene command is unsupported for its device.")
            if step["command"] in {"dim", "set_speed", "set_position"}:
                percentage(step.get("value"), "Scene value")
            if step["command"] == "change_color" and (
                    not isinstance(step.get("value"), str)
                    or not re.fullmatch(r"[a-zA-Z ]{1,30}", step["value"])):
                raise CommandError("Invalid scene color.")
    # An omitted optional scene map must have the same contract as an empty one.
    # Every controller interface can then read and manage scenes safely.
    return {**deepcopy(raw), "scenes": deepcopy(scenes)}


class Home:
    """Local simulator. State changes commit atomically after all checks pass."""

    def __init__(self, *, state_file: Path | None = None, code: str = "2468",
                 clock: Callable[[], float] = time.time):
        if not isinstance(code, str) or not 4 <= len(code) <= 128 or not code.isprintable():
            raise CommandError("The simulator control code must contain4–128printable characters.")
        self.state_file = Path(state_file) if state_file else None
        self.code = code
        self.clock = clock
        self.lock = threading.RLock()
        self.events: list[dict[str, Any]] = []
        self.revision = 0
        self.instance_id = uuid.uuid4().hex
        if self.state_file and self.state_file.exists():
            try:
                raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                raise CommandError("Cannot read saved state; it was left unchanged.") from e
        else:
            raw = json.loads(files("smart_home").joinpath("data/home.json").read_text())
        self.data = validate_document(raw)
        self.tick()

    def _persist(self, data: dict[str, Any]) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.state_file.parent,
                                             prefix=".smart-home-", delete=False) as f:
                temp = Path(f.name)
                json.dump(data, f, indent=2, allow_nan=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            temp.replace(self.state_file)
        finally:
            if temp is not None and temp.exists():
                temp.unlink()

    def _commit(self, data: dict[str, Any], message: str, changed: list[str]) -> Result:
        self._persist(data)  # Disk failure does not produce a false success or memory-only state.
        self.data = data
        self.revision += 1
        self.events.insert(0, {"time": self.clock(), "message": message,
                               "devices": changed, "mode": "simulation"})
        del self.events[30:]
        return Result(True, message, tuple(changed))

    def tick(self) -> None:
        with self.lock:
            new = deepcopy(self.data)
            due = []
            for d in new["devices"]:
                if d.get("auto_close_at", math.inf) <= self.clock():
                    d["state"] = "closed"
                    d.pop("auto_close_at", None)
                    due.append(d["id"])
            if due:
                self._commit(new, "Open devices closed automatically in the simulator.", due)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            self.tick()
            return {**deepcopy(self.data), "mode": "simulation", "revision": self.revision,
                    "instance_id": self.instance_id,
                    "events": deepcopy(self.events), "physical_hardware_connected": False}

    def _apply(self, data: dict[str, Any], op: Operation, code: str | None) -> str:
        d = next((x for x in data["devices"] if x["id"] == op.device_id), None)
        if not d:
            raise CommandError("That device does not exist.")
        kind, cmd = d["type"], op.command
        if cmd not in OPERATIONS[kind]:
            raise CommandError(f"{d['name']} does not support {cmd}.")
        if cmd in {"unlock", "disarm"} and code != self.code:
            raise CommandError("Enter the control code before unlocking or disarming.")
        armed = any(x["type"] == "alarm" and x["state"] == "armed" for x in data["devices"])
        if kind == "door":
            if cmd in {"unlock", "open"} and armed:
                raise CommandError("Disarm the alarm before opening or unlocking a door.")
            if cmd == "open" and d["locked"]:
                raise CommandError("Unlock the door before opening it.")
            if cmd == "lock" and d["state"] == "open":
                raise CommandError("Close the door before locking it.")
            if cmd in {"lock", "unlock"}:
                d["locked"] = cmd == "lock"
            else:
                d["state"] = "open" if cmd == "open" else "closed"
                if cmd == "open":
                    d["auto_close_at"] = self.clock() + 5
                else:
                    d.pop("auto_close_at", None)
        elif kind == "alarm":
            if cmd == "arm" and any(x["type"] == "door" and
                                       (not x["locked"] or x["state"] != "closed")
                                       for x in data["devices"]):
                raise CommandError("Close and lock every door before arming the alarm.")
            d["state"] = "armed" if cmd == "arm" else "disarmed"
        elif kind == "light":
            if cmd == "dim":
                d["brightness"] = percentage(op.value, "Brightness")
                d["state"] = "on" if op.value else "off"
            elif cmd == "change_color":
                if not isinstance(op.value, str) or not re.fullmatch(r"[a-zA-Z ]{1,30}", op.value):
                    raise CommandError("Color must be a short color name.")
                d["color"] = op.value.lower()
            else:
                d["state"] = "on" if cmd == "turn_on" else "off"
                if cmd == "turn_on" and d["brightness"] == 0:
                    d["brightness"] = 100
        elif kind == "fan":
            if cmd == "set_speed":
                d["speed"] = percentage(op.value, "Speed")
                d["state"] = "on" if op.value else "off"
            else:
                d["state"] = "on" if cmd == "turn_on" else "off"
                d["speed"] = (d["speed"] or 50) if cmd == "turn_on" else 0
        elif kind == "curtain":
            d["position"] = (percentage(op.value, "Position") if cmd == "set_position"
                             else (100 if cmd == "open" else 0))
            d["state"] = "open" if d["position"] else "closed"
        elif kind == "bin":
            d["state"] = "open" if cmd == "open" else "closed"
            if cmd == "open":
                d["auto_close_at"] = self.clock() + 3
            else:
                d.pop("auto_close_at", None)
        return f"{d['name']}: {cmd.replace('_', ' ')}" + (
            f" → {op.value}" if op.value is not None else "")

    def execute(self, operations: list[Operation], *, code: str | None = None,
                label: str | None = None) -> Result:
        with self.lock:
            self.tick()
            if not operations or len(operations) > 100:
                return Result(False, "A command needs 1–100 operations.")
            new = deepcopy(self.data)
            try:
                messages = [self._apply(new, op, code) for op in operations]
                validate_document(new)
                return self._commit(new, label or "; ".join(messages),
                                    list(dict.fromkeys(op.device_id for op in operations)))
            except (CommandError, OSError) as e:
                return Result(False, str(e))

    def scene(self, name: str, *, code: str | None = None) -> Result:
        with self.lock:
            steps = self.data["scenes"].get(name)
            if not steps:
                return Result(False, "That scene does not exist.")
            return self.execute([Operation(**s) for s in steps], code=code,
                                label=f"Scene activated: {name.replace('_', ' ')}")

    def add_device(self, config: dict[str, Any]) -> Result:
        with self.lock:
            new = deepcopy(self.data)
            new["devices"].append(deepcopy(config))
            try:
                validate_document(new)
                return self._commit(new, f"Device added: {config['name']}", [config["id"]])
            except (CommandError, OSError) as e:
                return Result(False, str(e))

    def remove_device(self, device_id: str) -> Result:
        with self.lock:
            if not any(d["id"] == device_id for d in self.data["devices"]):
                return Result(False, "That device does not exist.")
            if any(s["device_id"] == device_id for steps in self.data["scenes"].values() for s in steps):
                return Result(False, "Remove this device from its scenes first.")
            new = deepcopy(self.data)
            new["devices"] = [d for d in new["devices"] if d["id"] != device_id]
            try:
                validate_document(new)
                return self._commit(new, f"Device removed: {device_id}", [device_id])
            except (CommandError, OSError) as e:
                return Result(False, str(e))

    def save_scene(self, name: str, steps: list[dict[str, Any]]) -> Result:
        with self.lock:
            new = deepcopy(self.data)
            new["scenes"][name] = deepcopy(steps)
            try:
                validate_document(new)
                return self._commit(new, f"Scene saved: {name.replace('_', ' ')}", [])
            except (CommandError, OSError) as e:
                return Result(False, str(e))

    def remove_scene(self, name: str) -> Result:
        with self.lock:
            if name not in self.data["scenes"]:
                return Result(False, "That scene does not exist.")
            new = deepcopy(self.data)
            del new["scenes"][name]
            try:
                return self._commit(new, f"Scene removed: {name.replace('_', ' ')}", [])
            except OSError as e:
                return Result(False, str(e))

    def replace_configuration(self, raw: dict[str, Any]) -> Result:
        with self.lock:
            try:
                new = validate_document(raw)
                return self._commit(new, "Home configuration imported into the simulator.",
                                    [d["id"] for d in new["devices"]])
            except (CommandError, OSError) as e:
                return Result(False, str(e))
