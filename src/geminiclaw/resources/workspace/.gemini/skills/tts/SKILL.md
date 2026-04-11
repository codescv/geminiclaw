---
name: tts
description: "Generate high-fidelity speech audio using text to speech with voice cloning and subtitles."
---

# Prerequisites
Make sure `tts` command is installed first with:
`which tts || uv tool install --default-index https://pypi.org/simple git+https://github.com/codescv/aigc_toolkit`.

# Parameters
- `--text`: The target text to synthesize. 
  - For best quality, you need to split the text into chunks using newlines (`\n`), where each chunk is 20-30 words (for languages like English) or characters (for languages like Chinese and Japanese). Combine sentences that are too short and split sentences that are too long. 
  - Make sure to strip non-spoken text. e.g. "マリオの映画(えいが)を見(み)た" -> "マリオの映画を見た"
- `--output`: Full path to the output `.wav` file.
- `--ref_audio` (Optional): Path to a 5-30 second clear reference audio file. Required for voice cloning.
- `--ref_text` (Optional): The exact text spoken in the reference audio. Required for voice cloning.
- `--srt` (Optional): Generate a `.srt` subtitles file.
- `--model_type` (Optional, default: `fishaudio`):
  - `qwen3`: Supports Chinese, English and Japanese. Doesn't support cross language voice cloning or emotion control.
  - `fishaudio`: Supports Chinese, English and Japanese. Supports **cross language voice cloning** (input text and ref text are in different languages) or **emotion control** (see below).

# Emotion Control (fishaudio Model ONLY, DOES NOT work for qwen3)
Fish Audio Model supports natural language emotion and style tags using square brackets `[ ]`. 
You can place them at the beginning of the text.

**Examples:**
- `[angry] Stop it! I told you I'm tired.`
- `[whisper] Be quiet, the baby is sleeping.`
- `[excited] Oh my god! This is amazing!`
- `[sad] I feel a bit lonely today.`
- `[laughing] Haha, that's actually quite funny!`
- `[warm] Can I help you with this?`

# Best Practice
Use the `stt` skill to check against the generated audio. If the output is garbage text, try again. Try at most 3 times.