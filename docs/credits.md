# Credits and dependencies

Smart Home System is an academic team project maintained by Alfarouk Salah
Elkashef. Contributor rights are described in [LICENSE.md](../LICENSE.md).

The core controller and local dashboard use the Python standard library.
Optional integrations use these packages and models:

| Integration | Project |
| --- | --- |
| Local speech input | [SpeechRecognition](https://pypi.org/project/SpeechRecognition/) and [PocketSphinx](https://pypi.org/project/pocketsphinx/) |
| Microphone input | [PyAudio](https://pypi.org/project/PyAudio/) and [PortAudio](https://www.portaudio.com/) |
| Speech output | [pyttsx3](https://pypi.org/project/pyttsx3/) with the operating system’s native driver |
| Face detection and comparison | [OpenCV Zoo YuNet and SFace](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7) |
| Serial requests and loopback | [pySerial](https://pyserial.readthedocs.io/) |

The face-model downloader pins the OpenCV Zoo commit, checks file size and
SHA256, and saves each upstream license. YuNet is MIT-licensed and SFace is
Apache-2.0-licensed. Dependency version and source records are in
[dependency-sources.json](dependency-sources.json).
