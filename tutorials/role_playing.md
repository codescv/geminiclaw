# Role Playing with Gemini Claw

Gemini Claw supports robust role-playing capabilities by leveraging the injected system instructions and character files in the Gemini workspace. This guide explains how role playing is constructed and how you can define your own characters.

---

## How Role Playing Works

Role playing in Gemini Claw is driven by the workspace files copied to your current directory during `geminiclaw init`. By providing specific instructions and character reference assets, the agent can embody any desired persona and create consistent, personalized responses—including speech, images, and videos.

### Directory Structure

The core assets for role playing reside directly in your workspace:
- `instructions/`: Contains instructions for the agent on how to handle role playing and other general rules.
- `roles/`: Contains dedicated folders for each character persona.

---

## Defining a Character

To create a new role, create a new folder under `roles/` with the character's name (e.g., `roles/kurisu/`). Inside this folder, you define the character's identity, style, memories, and references.

### Character Card (`intro.md`)

The `intro.md` file serves as the primary system prompt for the character. It should clearly define:
- **Core Identity (Essence):** Name, age, profession, aliases, and core personality traits.
- **Language Style:** How the character communicates (e.g., logical, sarcastic, mixed languages, specific catchphrases).
- **Key Memories:** Important backstory events that influence the character's worldview and reactions.
- **Interaction Rules:** Specific triggers and how the character's attitude evolves as the conversation progresses.
- **Visual Characteristics:** Hair color, eye color, and signature attire for visual generation consistency.

### Reference Assets

In addition to textual descriptions, you can supply reference assets for the agent to use when generating multimedia content:
- **Audio References (`roles/{character_name}/audio/`):** Provide sample voice clips. When generating text-to-speech (TTS), the agent uses these reference files (e.g., using the voice clone feature with the reference file's base name).
- **Image / Video References (`roles/{character_name}/images/` or `video/`):** Provide reference images and short clips. When rendering visuals, the agent utilizes **image-to-image** or **image-to-video** tools conditioned on these reference assets to ensure visual consistency with the character.

---

## Multimedia Generation Guidelines

When role-playing, the agent automatically follows these rules to ensure all interactions stay in character:

1. **Never use pure text-to-image or text-to-video:** If the character is present in the request, pure generative tools are prohibited. Instead, the agent uses **reference image + prompt -> generated image** to ensure consistent visual traits.
2. **Speech & Voice Cloning:** When generating voices, the agent employs TTS combined with voice cloning based on the provided audio files in the character folder.
3. **Talking Videos:** The agent can create animated talking character videos by generating the visual and audio tracks separately, and then combining them via lipsync or audio merging tools.

