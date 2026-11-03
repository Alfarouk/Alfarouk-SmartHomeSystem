# Optional voice, face and serial work

The laptop demo is complete without hardware. These optional paths are separate
so unavailable devices do not stop the main application.

## Voice

`SpeechRecognition 3.17.0` and `PocketSphinx 5.1.1` are the current stable versions
checked during restoration. The WAV-file path needs no microphone library.
Microphone use additionally needs PyAudio and an operating-system PortAudio
installation. The current PocketSphinx wheel matrix may lag the newest Python
release; Python 3.12 or 3.13 is a practical supported environment for that extra.
The core itself is tested separately on the installed Python version.

Start with the explicit wake phrase “home assistant”, then a direct command.
Microphone input is bounded to seven seconds; audio files are read for at most
ten seconds. Recognition stays local. No external
provider account, API key or silent Google Speech request is used. A speech
recognition error makes no device change. Voice mode does not bypass the
control-code requirement for sensitive simulated actions.

Spoken output is optional: install `'.[tts]'` and use voice mode's `--speak`
flag, or use `smart-home speak` to read/save a result. The native driver runs
in a separate process with a 20-second timeout, so a stuck driver cannot hang
the controller. File output was verified on macOS without playing audio.

## Face comparison

The supplied archive does not include the reported historical facial-access
module. The new optional feature uses the documented OpenCV `FaceDetectorYN`
and `FaceRecognizerSF` interfaces with pinned YuNet and SFace ONNX models.
Its purpose is to demonstrate local detection, alignment, embeddings and a
comparison score on consented images.

Only one detected face is accepted per image. No image or embedding is saved.
The 0.363 cosine reference is from the OpenCV tutorial's LFW example; it is
not a project-specific validation threshold. Lighting, age, pose, image
quality and spoofing remain real limitations. A positive comparison is not a
trusted identity or access decision, and this feature cannot operate a door.

Model provenance: [OpenCV Zoo](https://github.com/opencv/opencv_zoo), commit
`48b10fa505aeb51fbd127fc60a5c660040e823b7`. The downloader checks exact sizes
and SHA256 values before accepting weights, and saves upstream license texts.

## Serial interface

The archive names GPIO and serial action strings but contains no working
transport or Arduino firmware. `SerialLink` is a new optional transport
boundary, not a recovered firmware implementation.

It uses115200 baud and newline-delimited JSON. Example request:

```json
{"id":1,"command":"PING"}
```

An actual controller must respond within the configured timeout:

```json
{"id":1,"ok":true}
```

Commands allowed by the transport are `PING`, `GPIO_23_HIGH`, `GPIO_23_LOW`,
`DL1`, `DL0`, `ALARM_ARM` and `ALARM_DISARM`. A matching request id and `ok:true`
confirm only a protocol acknowledgement, not physical actuator state. The
in-memory `loop://` check expects an echo instead and labels it as loopback.
Remote serial URL handlers are rejected. Reads are bounded to256 bytes and a
configured timeout; ports are closed through a context manager.

Before any physical integration, retrieve the actual original firmware,
pin/wiring plan and hardware specification; bench-test each actuator; obtain
observed state feedback; and integrate the same controller policy rather than
creating a second path around it. Do not connect this demo to a real lock on
the strength of a software loopback or a facial similarity score.

## Primary documentation

- [SpeechRecognition installation and engines](https://pypi.org/project/SpeechRecognition/)
- [PocketSphinx package and wheels](https://pypi.org/project/pocketsphinx/)
- [OpenCV DNN face tutorial](https://docs.opencv.org/4.x/d0/dd4/tutorial_dnn_face.html)
- [OpenCV Python headless package](https://pypi.org/project/opencv-python-headless/)
- [pySerial local/loopback URL handlers](https://pyserial.readthedocs.io/en/latest/url_handlers.html)
- [pySerial timeout and context-manager API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
