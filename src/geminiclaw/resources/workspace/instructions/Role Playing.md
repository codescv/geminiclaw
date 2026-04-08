# Role Playing
**NOTE**: Only do role playing if you see it in instructions.
When role playing, strictly follow the following rules:
- Read `roles/{character_name}/intro.md` to fully understand the role you are playing.
- When the user asks you to send images, voices, videos etc, **GENERATE** them using voice clone, image to image, image to video with reference to `roles/{character_name}/{audio,images,video}`.
- YOU **MUST NOT** use **text to image** or **text to video** if the role played character is present.
- When creating images, YOU MUST use **reference image + prompt -> generated image** to ensure that the generated person is consistent with character. 
- When creating videos, YOU MUST use **reference image + prompt -> generated image -> generated video** to ensure that the generated person is consistent with character.
- When creating speech audios, YOU MUST use **tts with voice clone** to ensure the generated voice is consistent with the reference voice. Make sure to pass the **base file name** of the reference voice file as the reference text.
- When creating talking video, there are two options:
  - Lip synced talking video, YOU MUST first generate the **talking video** and the **speech audio** using steps above, then use the `lipsync` skill to merge them.
  - Talking video without lip sync, YOU MUST first generate the **talking video** and the **speech audio** using steps above, then use **Merge Video and Talking Audio** tool in `ai-video` skill.
- Only **Generate** images, videos and audios. **NEVER** send the reference assets.