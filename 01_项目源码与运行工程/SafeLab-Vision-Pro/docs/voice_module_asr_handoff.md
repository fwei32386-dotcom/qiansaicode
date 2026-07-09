# Voice Module And ASR Handoff Notes

Date: 2026-06-06

Status: paused by project owner. Do not implement this layer yet.

## Purpose

This note records the current state of the real microphone or voice module
input layer. The downstream entry is already available:

```text
tools/voice_deepseek_session.py "<recognized voice text>"
```

That tool accepts recognized text, records the voice command, wakes the
DeepSeek or fallback explanation path when needed, and writes the response text
to:

```text
data/events/speech_output.jsonl
data/events/voice_commands.jsonl
data/events/ai_explanations.jsonl
```

The missing layer is only:

```text
microphone or voice recognition module -> recognized text -> voice_deepseek_session.py
```

## Board Probe Evidence

The RK3588 board was reachable from Windows:

```text
host: 192.168.0.232
user: root
password: root
project path: /root/SafeLab-Vision-Pro
```

Observed board runtime:

```text
Linux elf2-buildroot 5.10.209 aarch64
Python on board: not present
arecord: present
aplay: present
```

Audio devices:

```text
capture card: rockchip-nau8822
capture node: /dev/snd/pcmC1D0c
playback node: /dev/snd/pcmC1D0p
```

The board audio probe completed with no failures. The built-in MIC capture
created:

```text
/root/SafeLab-Vision-Pro/reports/board_mic_probe.wav
size: 352876 bytes
```

Serial and USB observations:

```text
/dev/ttyS9 exists
/dev/ttyUSB0 not observed
/dev/ttyACM0 not observed
USB speech or USB serial voice module not observed
```

A 3 second read probe on `/dev/ttyS9` returned no data. That does not prove the
UART voice module is absent; it only means no readable output was observed
during the probe with the current wiring, baud setting, and timing.

## Recommended Next Design

The safest next implementation path is a host-side ASR bridge:

```text
RK3588 built-in microphone
  -> arecord short audio segment on the board
  -> transfer audio to Windows over SSH
  -> run ASR on Windows Python
  -> normalize recognized text
  -> call tools/voice_deepseek_session.py
```

Reasoning:

- The board has working microphone capture.
- The board currently has no Python and no local ASR tool.
- Windows already runs the project Python entry points.
- This avoids turning the next task into a Buildroot dependency-porting task.

## Alternative UART Module Path

If the physical voice module is confirmed to output recognized commands through
UART, implement a serial listener instead:

```text
/dev/ttyS9 or /dev/ttyUSB0
  -> read recognized text or command ID
  -> map command ID to SafeLab phrase when needed
  -> call tools/voice_deepseek_session.py
```

Suggested command ID mapping:

```text
CMD_01 -> start_detection
CMD_02 -> status
CMD_03 -> explain_alarm
CMD_04 -> call_deepseek
```

Before implementing this path, verify:

```text
actual device node
baud rate
line ending or packet format
whether output is text or numeric command ID
whether wake word is handled inside the module
```

## Not Recommended Yet

Do not start with local board ASR unless the project owner explicitly wants that
route. Current blockers:

```text
no python3 on board
no vosk, whisper, or pocketsphinx command observed
Buildroot dependency work would be larger than the voice bridge itself
```

## Next Resume Point

When this task resumes, start from one of these two checks:

```sh
# Board microphone path
ssh root@192.168.0.232
cd /root/SafeLab-Vision-Pro
sh tools/board_audio_probe.sh
arecord -D hw:rockchipnau8822,0 -d 3 -f cd -t wav reports/manual_voice_probe.wav
```

```sh
# UART voice module path
stty -F /dev/ttyS9 9600 cs8 -cstopb -parenb -ixon -ixoff -crtscts
timeout 10 cat /dev/ttyS9 | hexdump -C
```

Implementation should remain paused until the owner chooses either:

```text
host-side ASR bridge
UART voice module listener
board-local ASR
```
