---
name: lipsync
description: Generate talking head video with lip sync.
---

# Prerequisites
Make sure the `wav2lip` command is installed with:
`which wav2lip || uv tool install --default-index https://pypi.org/simple git+https://github.com/codescv/Easy-Wav2Lip-MacOS --python 3.10`

# Arguments:
Run `wav2lip` with the following arguments:

- `--face`: Filepath of video/image that contains faces to use.
- `--audio`: Filepath of video/audio file to use as raw audio source.
- `--outfile`: Video path to save result.
- `--quality`: Choose Improved by default.