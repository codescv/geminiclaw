---
name: ai-image
description: All in one image skill with image generation and editing.
---

# Prerequisites
Make sure the `generate_image` command is installed first with:
`which generate_image || uv tool install --default-index https://pypi.org/simple git+https://github.com/codescv/aigc_toolkit`.

# Parameters

- `--prompt PROMPT`: The text prompt to generate the image from.
- `--output OUTPUT`: Output file name/path.
- `--model MODEL`: The model ID to use.
- `--aspect-ratio {1:1,16:9,9:16,3:4,4:3}`: Aspect ratio of generated image.
- `--image IMAGE`: Path to an input image for image-to-image/editing operations.

## Examples
Text-to-Image:
`--prompt "A hyperrealistic render of a neon jellyfish floating in a cyber forest" --output "neon_jellyfish.png" --aspect-ratio "9:16"`

Image-to-Image:
`--prompt "Change the style to a watercolor painting" --image "neon_jellyfish.png" --output "watercolor_jellyfish.png" --aspect-ratio "16:9"`