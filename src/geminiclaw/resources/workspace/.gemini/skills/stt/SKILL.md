---
name: stt
description: Transcribe audio speech to text or generate subtitle (.srt) files. Use this to process voice messages.
---

# Prerequisites
Make sure the `stt` command is installed with the package:
`which stt || uv tool install --default-index https://pypi.org/simple git+https://github.com/codescv/aigc_toolkit`.

# Parameters
- `--audio`: The full path to the input audio file.
- `--output` (Optional): The path to save the output text or `.srt` file. If not specified, prints to standard output.
- `--srt` (Optional): Force the output as SubRip Subtitle format (`.srt`). This is automatically inferred if `--output` ends with `.srt`.
- `--model` (Optional, default: `mlx-community/whisper-large-v3-turbo`): The whisper model ID or local path to use.

# Examples

## Transcribe Audio to Plain Text
```bash
stt --audio /path/to/audio.wav
```

## Save Transcription to a Text File
```bash
stt --audio /path/to/audio.wav --output /path/to/transcription.txt
```

## Generate Subtitle (SRT) File
```bash
stt --audio /path/to/audio.wav --output /path/to/subtitles.srt
```