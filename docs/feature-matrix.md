# Features and interfaces

Text commands, the browser dashboard and the Python API call the same
controller. Voice, face and serial tools are installed separately.

| Feature | Interface | Behavior |
| --- | --- | --- |
| Commands and help | Text CLI, dashboard form, voice transcript | Direct supported phrases execute; unclear wording makes no change. |
| Lights | Text, device cards, `Home.execute` | On/off, brightness and color; named devices and rooms. |
| Doors | Text, door cards, `Home.execute` | Lock/unlock, open/close and five-second auto-close; shared code/alarm policy. |
| Alarm | Text, alarm card, `Home.execute` | Arm/disarm with code and door-state checks. |
| Curtains | Text, device cards, `Home.execute` | Open/close and percentage position. |
| Fan and bin | Text, device cards, `Home.execute` | Fan speed/on/off; bin open/close and three-second auto-close. |
| Device management | `smart-home device`, `Home.add_device/remove_device` | Schema, ID and scene-reference checks. |
| Configuration | `--state-file`, `smart-home config`, `Home.replace_configuration` | Explicit JSON import/export with atomic saves. |
| Scenes | Cards, text, `smart-home scene`, `Home.scene/save_scene/remove_scene` | Validated operations applied as one transaction. |
| Status | CLI, dashboard, state API | Whole-home, named-device and room status, without device changes. |
| Offline speech | `smart-home voice`, microphone or WAV file | Explicit wake phrase and bounded local recognition. |
| Spoken output | Voice `--speak`, `smart-home speak`, Python `speak()` | Optional native-driver output with timeout. |
| Face comparison | `smart-home face-compare` | Local one-face image comparison; no door operation. |
| Serial transport | `smart-home serial-loopback`, `SerialLink` | Bounded JSON requests with matching response IDs; hardware firmware is separate. |

## Device and scene JSON

Example `new-device.json`:

```json
{"id":"desk","name":"Desk Light","room":"Office","type":"light","state":"off","brightness":70,"color":"white"}
```

Example `study-scene.json`:

```json
[{"device_id":"desk","command":"dim","value":70}]
```

Configuration export contains `name`, the `devices` list and the `scenes`
mapping. It does not include the control code or command history. Device
families and their valid commands are defined once in `controller.py`.

## Python API

```python
from pathlib import Path
from smart_home.controller import Home, Operation
from smart_home.commands import process

home = Home(state_file=Path("state.json"))
print(process(home, "turn on Main Light in Living Room").to_dict())
print(home.execute([Operation("curtain_1", "set_position", 50)]).to_dict())

added = home.add_device({
    "id": "desk", "name": "Desk Light", "room": "Office",
    "type": "light", "state": "off", "brightness": 70, "color": "white"
})
if added.ok:
    home.save_scene("study", [{"device_id": "desk", "command": "dim", "value": 70}])
    print(home.scene("study").to_dict())
    home.remove_scene("study")
    home.remove_device("desk")

print(home.snapshot())
```

The API returns a success flag, a message and the IDs of changed devices.
Use the methods above rather than changing `home.data` directly. Saving a scene
does not run it. Door and alarm rules are checked when the scene runs.
