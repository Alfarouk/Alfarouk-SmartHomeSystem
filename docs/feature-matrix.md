# Source features and current interfaces

The supplied archive contains two application branches. This table separates
their implemented behavior from configuration-only entries and from the
candidate's reported hardware work.

| Source feature | Supplied branch | Current usable interface | Result or intentional change |
| --- | --- | --- | --- |
| Phrase samples and synonyms | `logic/analyzer.py`, `config/commands.yaml` | Text CLI, voice transcript, dashboard command form | Direct supported phrases execute; ambiguous security wording is clarified; fuzzy wording suggests only |
| Text/voice console choice | `tests/console.py` | `smart-home console` / `smart-home voice` | Separate modes replace recursive switching |
| Lights on/off | Both | Text, device cards, `Home.execute` | Preserved; rooms and names resolve explicitly |
| Door lock/unlock | Both | Text, door card, `Home.execute` | Preserved; unlock requires demo code and disarmed alarm |
| Door open/close | Recovered `AI.py` | Text, door card, `Home.execute` | Preserved; locked door cannot open and open door cannot lock |
| Five-second door auto-close | Recovered `AI.py` | Any open-door command, polled state | Preserved with a bounded clock deadline instead of unowned timer threads |
| Alarm arm/disarm | Small simulator branch | Text, alarm card, `Home.execute` | Preserved; configured code requirement is enforced; disarm is no longer incorrectly blocked merely because the door is locked |
| Device names and rooms | Recovered `AI.py` / both JSON files | Named/room text commands, room filter, state API | Preserved and validated |
| Light dimming | Recovered `AI.py` | `dim Main Light to 30`, slider, typed API | Preserved; range 0–100 enforced |
| Light color | Recovered `AI.py` | `set Main Light color to blue`, typed API | Preserved |
| Curtain open/close/position | Recovered `AI.py` | Text, card/slider, typed API | Preserved; range 0–100 enforced |
| Device add/remove | Recovered `AI.py` | `smart-home device`, `Home.add_device/remove_device` | Preserved with duplicate-id/schema checks and scene-reference protection |
| Configuration load/save | Recovered `AI.py` | `--state-file`, `smart-home config`, `Home.replace_configuration` | Preserved; explicit paths and atomic writes replace current-directory dependence and silent reset |
| Movie/morning/night scenes | Both JSON files, implemented by `AI.py` | Scene cards, text command, `Home.scene` | Both configurations reconciled into one complete set; atomic execution replaces partial changes |
| Scene add/edit | Recovered `AI.py` | `smart-home scene save`, `Home.save_scene` | Preserved; scene validation added |
| Scene removal | Not in original | `smart-home scene remove`, `Home.remove_scene` | New safe management support |
| Help and status | Both | Text CLI, command form, `smart-home status` | Preserved; help/status do not alter device state |
| Named device/room status | Recovered `AI.py` | `status of Front Door`, `status of Living Room` | Preserved, including lock state |
| Wake-phrase speech | Recovered `AI.py` | `smart-home voice --wake-word "home assistant"` | Broken split call replaced with an explicit opening phrase and bounded recording |
| Speech recognition | Both | Microphone or `--audio-file` | Local PocketSphinx replaces implicit Google upload; errors and unclear speech make no change |
| Spoken response | Both | Voice `--speak`, `smart-home speak`, Python `speak()` | Preserved as an optional isolated native-driver path with timeout |
| Fan/bin | Only small JSON configuration, no supplied device implementation | Device cards, commands, typed API | New simulated implementation, not claimed as recovered original code |
| 30-minute light duration / 30-second arming delay | YAML parameter declarations, not consumed by either supplied runtime | No hidden automatic schedule | Kept as source context, not claimed as a working recovered timer; only demonstrated source auto-close behavior is restored |
| Speaker/camera/appliance enum members | Declared by `AI.py`, not implemented | No pretend device implementation | Recorded as unimplemented source declarations |
| Facial recognition / Pi GPIO / Arduino | Candidate report; actual modules not supplied | Optional new face comparison and serial diagnostic | Reported historical work retained; these new modules are not proof of the old physical implementation |

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

The API returns one explicit success/refusal result. Do not mutate `home.data`
directly; use the validated methods. A scene is saved independently of whether
its current door/alarm policy would permit execution. Those policies are
checked when it actually runs.
