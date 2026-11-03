"""New optional bounded serial transport; not a recovered Arduino implementation."""
from __future__ import annotations

import json
import re

from .controller import CommandError

SUPPORTED = {"PING", "GPIO_23_HIGH", "GPIO_23_LOW", "DL1", "DL0", "ALARM_ARM", "ALARM_DISARM"}


class SerialLink:
    def __init__(self, port: str, *, timeout: float = 1.0):
        if not 0.05 <= timeout <= 10:
            raise CommandError("Serial timeout must be0.05–10seconds.")
        if port != "loop://" and not re.fullmatch(r"(?:COM\d+|/dev/[A-Za-z0-9._-]+)", port):
            raise CommandError("Use a local serial port or loop://, not a remote transport URL.")
        try:
            import serial
        except ImportError as e:
            raise CommandError("Install the serial extra: pip install '.[serial]'.") from e
        self.port = port
        self.serial = serial.serial_for_url(port, baudrate=115200, timeout=timeout,
                                           write_timeout=timeout)

    def exchange(self, command: str, request_id: int = 1) -> dict[str, object]:
        if command not in SUPPORTED or type(request_id) is not int or not 0 < request_id < 2**31:
            raise CommandError("Unsupported serial command or request id.")
        frame = {"id": request_id, "command": command}
        self.serial.reset_input_buffer()
        self.serial.write((json.dumps(frame, separators=(",", ":")) + "\n").encode())
        self.serial.flush()
        raw = self.serial.read_until(b"\n", size=256)
        if not raw.endswith(b"\n"):
            raise CommandError("Serial response timed out or exceeded256bytes.")
        try:
            reply = json.loads(raw)
        except ValueError as e:
            raise CommandError("Serial response is not valid JSON.") from e
        if not isinstance(reply, dict) or reply.get("id") != request_id:
            raise CommandError("Serial response does not match the request.")
        if self.port == "loop://":
            if reply != frame:
                raise CommandError("Loopback response differs from the transmitted frame.")
            return {"ok": True, "mode": "serial_loopback", "physical_hardware_tested": False,
                    "echo": reply}
        if reply.get("ok") is not True:
            raise CommandError("The connected controller did not acknowledge the command.")
        return {"ok": True, "mode": "serial_acknowledgement", "reply": reply,
                "physical_device_state_verified": False}

    def close(self) -> None:
        self.serial.close()

    def __enter__(self) -> "SerialLink":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
