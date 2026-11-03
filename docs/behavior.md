# Behavior and validation

All interfaces use the same controller policies. A successful response means
the requested simulation change was committed. A refusal leaves state unchanged.

| Area | Behavior |
| --- | --- |
| Command matching | Exact grammar and explicit device/room resolution. Fuzzy matches suggest wording only. |
| Unclear instructions | Negated, conditional or ambiguous commands make no device change. |
| Help and status | Read-only operations; no device state is changed. |
| Lights, curtains and fan | Whole-number values from 0 to 100. Booleans and nonfinite values are refused. |
| Door | A locked door cannot open. An open door cannot lock. Opening requires a disarmed alarm. |
| Unlock and disarm | Require the configured simulator control code. Codes are excluded from saved state and activity. |
| Auto-close | Doors close after five seconds and bins after three seconds, using clock deadlines without timer threads. |
| Scenes | Every operation validates on a copy before the complete scene commits. A failure makes no partial change. |
| Device management | Duplicate IDs, invalid schemas and removal of a scene-referenced device are refused. |
| Persistence | Explicit state-file paths and atomic saves. Invalid files are rejected; a save failure prevents a success response. |
| Voice | Optional bounded recognition feeds the same command parser. Recognition errors do not change devices. |
| Face and serial tools | Run separately from the dashboard and do not bypass controller policy. |

The standard configuration supports lights, doors, curtains, a fan, a bin and
an alarm. It includes movie-time, morning and night scenes. Speaker, camera and
other appliance controllers are not implemented device families.

The dashboard is a complete laptop simulation. Physical wiring, electrical
safety, actuator feedback and access-control performance require separate
hardware integration and testing. See [hardware.md](hardware.md).
