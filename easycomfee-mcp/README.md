# EasyComfee MCP

Lets an AI app generate images and videos with EasyComfee by chatting. It is an **MCP**
server, so it works with any MCP client that runs local servers: LM Studio (with an open-weights
model), Claude Desktop, Cursor, Codex, VS Code. It only calls EasyComfee's own local API (port 8600): jobs use the
same queue, show up in the gallery and respect the VRAM guard.

## Step by step (LM Studio, free, on your GPU)

1. **Open EasyComfee** and leave it running. The AI app can only use it while it is open.
2. Go to **Config Models → Connect your AI · MCP** and press **Set up**. It builds a small
   Python environment and adds the `easycomfee` entry to the AI apps it finds (LM Studio,
   Claude Desktop, Cursor, Codex). A `.bak` copy of each config is kept and your other MCP
   servers stay. If your app is not listed, press **Copy config** and paste it into its MCP settings (JSON; Codex uses TOML, so for
   Codex use the **Connect** button).
3. **Restart the AI app.** It only reads its MCP list when it starts.
4. In **LM Studio**, check the entry: *Developer → mcp.json* should list `easycomfee`.
5. **Load a model that supports tool use.** In LM Studio's model list these have a blue
   wrench icon. Use a mid-size one (about 9B or more): very small models get the arguments
   wrong, and heavy quantizations (Q1/Q2) break tool calls. Qwen3.5 9B (Q4_K_M) worked well.
6. Open a **new chat** with that model and turn the `easycomfee` switch on (plug/tools icon
   near the message box).
7. Ask: *"List the EasyComfee image models."* Then: *"Generate a red apple on a table with
   qwen21."* LM Studio shows each tool call and asks you to press **Proceed**. Read the
   `model` field before you approve a `generate`.
8. The image is saved in `~/EasyComfee-mcp` and also shows up in the EasyComfee gallery.

Tips:
- Do **not** tick "Always allow any tool". Allowing only `list_models` is fine.
- Local models cost nothing. Paid (API) models stay blocked until you raise the spending limit
  below.
- If every call fails, EasyComfee is probably closed. The tool error says it is not answering
  on port 8600.
- A big chat model and a generation share your VRAM. If the card struggles, eject the chat
  model before heavy video.
- **VRAM is shared, so size the pair.** On a 16 GB card, a 7 GB chat model (Qwen3.5 9B, Q4)
  plus a 9B image model (Flux 2 Klein) did not fit: VRAM hit 100%, the first step took minutes
  and the job looked stuck (it was only slow). Ejecting the chat model let it finish at once.
  Rules of thumb: with a 9B chat model, stay with light image models (`krea`, `sdxl`,
  `zimage`, `flux1s`); for `klein`, `flux2dev`, `qwen21` at 2K or video, use a smaller chat
  model (3–4B) or eject it while the job runs. The job keeps running in EasyComfee and the
  result shows up in its gallery either way.
- Settings go in `options` with the app's exact names, e.g. `{"proporcao": "16:9"}`. A wrong
  name (like `aspect_ratio`) is rejected instead of silently ignored, and every result reports the
  real `size` of the image.
- **Reference images.** The AI calls `upload_reference` with the path of an image (one you gave it,
  or a result saved in `~/EasyComfee-mcp`) and passes the returned name in
  `options: {"referencias": [name]}`. Edit models (`list_models` kind `edit`) take 1 to 10 images;
  for video use `model: "video"` with `modo_video: "imagem"` (first frame) or
  `"primeiro_ultimo"`. Only real images are accepted, and file paths are never accepted
  straight in `referencias`.
- Long jobs: `generate` waits about 40 s and then returns a `job_id` with `state` set to
  `executando`. The AI should call `job_status` with that same id (not `generate` again) until
  `state` is `pronto`. If the chat is lost, the finished image is still in the gallery and in
  `~/EasyComfee-mcp`.

## Tools

| Tool | What it does |
|---|---|
| `status` | Is the app up, local or cloud engine, what is generating |
| `list_models` | Model ids: image (local and cloud), edit, video |
| `estimate_cost` | Price before running (free on your GPU) |
| `upload_reference` | Send a local image (png/jpg/webp) to use as a reference: edit, restyle, keep a character, first frame of a video |
| `generate` | Run a model; waits ~40 s and, if not done, returns a `job_id` |
| `job_status` | Waits up to 40 s more; when done, saves the files in `~/EasyComfee-mcp` |
| `list_jobs` | The most recent jobs |
| `set_engine` | Switch `local` / `nuvem` (refused while something generates) |

## Cost guard

Local generation is free and runs at once. A job that costs credits (API models, cloud GPU)
runs only if its price is within **AI spending limit** (US$ per generation), which you set in
Config Models → Connect your AI. It is **0 by default**: nothing paid. The AI cannot change
the limit, and a job with an unknown price is always refused. The server never reads or
returns your Comfy Cloud key.

To allow paid models, pick a limit in **AI spending limit** (for example US$ 0.25 each). Anything
within it runs without asking you again, so keep it small and set it back to **Off** when you
are done. Above the limit, the AI is told the price and has to stop.

## Test

```bash
server/.venv/Scripts/python.exe tests/smoke_test.py          # no generation
server/.venv/Scripts/python.exe tests/smoke_test.py --gerar  # one small local image
```

## ChatGPT

Not supported. ChatGPT only connects to remote MCP servers over public HTTPS, and exposing
EasyComfee (and your spending) to the internet is not something this project does for you.
