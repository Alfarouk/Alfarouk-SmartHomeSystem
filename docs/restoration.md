# What changed in the restoration

The original archive is a useful starting point, but it was not a portable
repository. It bundled a Windows Python environment, caches and IDE files,
and hid one of its own application files inside that environment.

## Recovered source behavior

The smaller branch provides YAML phrase samples, a fuzzy analyzer, a simulated
light/door/alarm backend and a text/voice console. Its second JSON configuration
lists additional devices and scenes that the small simulator does not consume.

The larger `AI.py` branch provides object-based lights, doors and curtains;
configurable rooms; add/remove device methods; scenes; dim/color/position
operations; wake-word speech; and a timed door auto-close. The restored
controller combines these ideas in one state flow instead of leaving two
contradictory implementations.

## Defects repaired

| Source problem | Current behavior |
| --- | --- |
| Substring matching can match `lock` inside `unlock` | Exact command grammar and explicit device resolution |
| Fuzzy/partial matches operate devices even with uncertainty or negation | Fuzzy matches suggest wording only; conditional/negated commands make no change |
| `text.split(1)` crashes wake-word parsing | Bounded, separate offline recognition feeds the same text parser |
| Inconsistent special-case handler routing and help adding a fake state entry in the small simulator | Help/status are read-only system actions |
| Alarm code requirement is listed but not enforced | Simulated unlock/disarm check a code; all interfaces share it |
| Console confirms actions even after a simulator refusal | A single result controls response, state and activity display |
| Scenes can partially apply before a later error | All operations validate on a copy before one commit |
| Invalid dim/curtain values accepted | Whole-number0–100 validation; booleans and nonfinite values rejected |
| Invalid/missing config may be silently replaced | Explicit configuration errors preserve the saved file |
| Device state and speech depend on current working directory | Packaged defaults and explicit state-file path |
| Text mode imports microphone/TTS libraries | Optional, lazy audio imports |
| Recursive text/voice mode switching | Simple CLI modes with clean exit |
| Unowned timer threads | Clock-based deadline evaluation with no extra timer services |

The fan/bin devices were present only in a supplied configuration, not the
larger device implementation. Their current simulated behavior is new
restoration work. The local dashboard, safe persistence, optional model-based
face comparison, serial framing, tests and CI are also new restoration work.
They do not establish Farouk's independent mastery of every new component.

## Features that still need physical evidence

No Raspberry Pi, Arduino, camera, microphone or home actuators were supplied
for this review. Software tests and a serial loopback cannot prove wiring,
electrical safety, real lock state, recognition accuracy in a real environment
or a historical physical installation. The project stays explicit about those
boundaries rather than inventing successful hardware tests.
