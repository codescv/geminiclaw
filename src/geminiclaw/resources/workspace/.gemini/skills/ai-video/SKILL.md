---
name: ai-video
description: All in one video editing skill with video generation, audio dubbing, subtitles etc.
---

This skill is for video generation and editing.
Every section is optional; use only what you need.

# Prerequisites
Make sure the `generate_video` command is installed first with:
`which generate_video || uv tool install --default-index https://pypi.org/simple git+https://github.com/codescv/aigc_toolkit`.

# Video Generation
Run `generate_video`for Video Generation.

Arguments:
- `--aspect-ratio`: Aspect ratio, {1:1,16:9,9:16,3:4,4:3} (default: use `9:16`)
- `--model`: Model to use, e.g. `veo-3.1-generate-001`, `veo-3.1-fast-generate-001` etc.
If the model doesn't exist, search for what model id Google Veo supports.
- `--image`: the input image for image-to-video generation.
- `--prompt`: the prompt for video generation.
- `--filename`: the output filename.

## Examples Usage
Generate text-to-video: 
`--prompt "A cyberpunk city at night with neon lights" --filename "output.mp4"`

Generate image-to-video (animate an image):
`--prompt "Make the character speak and smile" -i "/path/to/image.png" --filename "output.mp4"`


# Burning Subtitles
Run `burn_subtitles` instead of raw `ffmpeg` filters.
Raw `ffmpeg` does NOT handle automatic line wrapping, which causes text to overflow.
This script uses `PingFang.ttc` or `Heiti` by default for excellent CJK/Japanese support.

## Arguments
- `--video_path`: Input video path
- `--srt_path`: Output SRT subtitle path
- `--out_path`: Output video path

# Merge Video and Talking Audio
When making talking videos, it's useful to loop the video and merge the audio with this command:

```bash
ffmpeg -y -stream_loop -1 -i "<video_path>" -i "<speech_audio_path>" -c:v libx264 -crf 28 -preset fast -c:a aac -map 0:v:0 -map 1:a:0 -shortest -fflags +genpts "<output_video_path>"
```