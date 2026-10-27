# ComfyUI workflows

The graphs EasyComfee sends to ComfyUI, exported in ComfyUI's API format by
`scripts/exportar_workflows.py` from the same Python builders the app uses
(`backend/workflows.py`, `videos_leves.py`, `ltx23.py`, `avatar.py`, `genjutsu.py`).

Drag a file onto the ComfyUI canvas to open it. Input file names (`input_video.mp4`,
`start_image.png`…) are placeholders: put your own files in ComfyUI's `input` folder
and pick them in the loader nodes. Models: install the matching package in the app's
Config Models, or see the main README for the download links.

| File | What it does |
|---|---|
| `image_krea2.json` | Image: text to image with Krea 2 Turbo |
| `image_zimage.json` | Image: Z-Image Turbo |
| `image_flux3_klein.json` | Image: FLUX 3 Klein |
| `image_flux1_dev.json` | Image: FLUX.1 dev |
| `image_flux1_krea_dev.json` | Image: FLUX.1 Krea dev |
| `image_flux2_dev.json` | Image: FLUX.2 dev (32B) |
| `image_hidream_i1_fast.json` | Image: HiDream I1 Fast |
| `image_chroma1_hd.json` | Image: Chroma1 HD |
| `image_sd35_large.json` | Image: SD 3.5 Large |
| `image_kandinsky5.json` | Image: Kandinsky 5 Image |
| `image_sdxl_light.json` | Image (light): SDXL, for 6-8 GB cards |
| `video_ltx25_text_or_image.json` | Video: LTX 2.5 text/image to video with sound (two-stage) |
| `video_ltx25_first_last.json` | Video: LTX 2.5 first & last frame |
| `video_ltx25_references.json` | Video: LTX 2.5 references (MSR), up to 4 people/objects + background |
| `video_ltx25_keyframes.json` | Video: LTX 2.5 keyframes, images pinned to chosen frames |
| `video_ltx25_ingredients.json` | Video: LTX 2.5 ingredients (reference sheet) |
| `video_ltx23_image.json` | Video: LTX 2.3 image / first & last frame |
| `video_light_ltxv2b.json` | Video (light): LTX-Video 2B distilled, 6-8 GB cards |
| `video_light_wan22_5b.json` | Video (light): Wan 2.2 TI2V 5B |
| `video_wan22_14b_text_or_image.json` | Video: Wan 2.2 14B, 4 steps (lightx2v), text or image to video |
| `video_wan22_14b_first_last.json` | Video: Wan 2.2 14B first & last frame |
| `video_hunyuan15.json` | Video: HunyuanVideo 1.5 720p, text or image to video |
| `video_kandinsky5.json` | Video: Kandinsky 5 Lite, text to video |
| `video_fasth3.json` | Video: FastH3 (MiniMax H3 distilled, 8 steps) |
| `lipsync_ltx23.json` | Lip Sync: a portrait and a voice track become a talking video (LTX 2.3) |
| `genjutsu_wan_animate2.json` | Genjutsu: Wan Animate 2, the photo performs the video's motion |
| `tool_depth_map.json` | Apps: video to depth map (Video Depth Anything), optional EXR frames |
| `vfx_day_to_night.json` | VFX app: Day to Night (LTX IC-LoRA) |
| `vfx_remove_people.json` | VFX app: Remove people (LTX IC-LoRA) |
| `vfx_add_water.json` | VFX app: Add water (LTX IC-LoRA) |
| `vfx_swap_character.json` | VFX app: Swap character (LTX IC-LoRA) |
| `vfx_expand_frame.json` | VFX app: Expand frame (LTX IC-LoRA) |
| `vfx_colorize.json` | VFX app: Colorize (LTX IC-LoRA) |
| `vfx_unblur.json` | VFX app: Unblur (LTX IC-LoRA) |
| `vfx_remove_compression.json` | VFX app: Remove compression (LTX IC-LoRA) |
| `vfx_refine_details.json` | VFX app: Refine details (LTX IC-LoRA) |
| `vfx_restore.json` | VFX app: Restore (LTX IC-LoRA) |
| `vfx_follow_depth.json` | VFX app: Follow depth (LTX IC-LoRA) |
| `vfx_render_to_video.json` | VFX app: 3D render to video (LTX IC-LoRA) |
