# EdenLive Pre-vis for Blender

**Block out a scene with cubes. Watch it become a world, live, as you move the camera.**

EdenLive Pre-vis is a Blender add-on that streams your viewport to
[Reactor](https://reactor.inc)'s **EdenLive** model and shows the generated world back inside
Blender, about a second behind your camera. Your scene controls the layout, the camera and the
motion. A reference image and a sentence or two of text control the look. When a shot feels
right, record the timeline and get an MP4.

| | |
|---|---|
| ![EdenLive output GIF placeholder](docs/media/eden_live_output_placeholder.svg) | ![Draft frame of the demo scene](docs/media/demo_draft_frame.png) |
| *Placeholder: drop a GIF of real EdenLive output here (`docs/media/eden_live_output.gif`).* | *What you build: primitives with flat colors.* |

It is made for pre-vis, look development and pitching: blocking that reads like a finished
frame in minutes, with the camera moves you already animated.

---

- [What you need](#what-you-need)
- [Install](#install)
- [Your first live world](#your-first-live-world)
- [Getting a good look](#getting-a-good-look)
- [Recording a shot](#recording-a-shot)
- [The panel](#the-panel)
- [Cost and privacy](#cost-and-privacy)
- [Troubleshooting](#troubleshooting)
- [For developers](#for-developers)

## What you need

- **Blender 4.2 or newer**, on Windows, macOS (Apple Silicon or Intel) or Linux.
- **A Reactor account.** EdenLive runs on Reactor's GPUs and is billed per minute of session
  time. Sign up at [reactor.inc](https://reactor.inc).
- **An internet connection.** Your draft frames go up, generated frames come back.

A dedicated GPU is nice to have, but the add-on only draws your viewport locally. The heavy
lifting happens on Reactor.

## Install

1. **Download** `eden_live_previs-<version>.zip` from the
   [latest release](https://github.com/willemhelmet/Eden-live-blender-reactor/releases/latest).
   One zip works on every platform.
2. **Drag the zip onto Blender's window** and confirm. (Or: **Edit > Preferences >
   Get Extensions > ⌄ > Install from Disk...**)
3. **Allow online access:** Edit > Preferences > System > Network > **Allow Online Access**.
   Blender blocks extensions from using the network until you do.
4. **Add your API key.** Open the sidebar in the 3D Viewport (press **N**), click the
   **EdenLive** tab, and paste your key into the field it shows. To get one: in the Reactor
   [dashboard](https://reactor.inc/dashboard), click your user icon, then **API Keys**, and create
   a key (it starts with `rk_`). The same field is in Edit > Preferences > Add-ons > EdenLive.

That's it. Nothing to pip-install, no terminal.

## Your first live world

Open the sidebar in the 3D Viewport (press **N**) and click the **EdenLive** tab.

1. **Build Demo Scene**, from the ⌄ menu in the panel header. Makes a jungle-temple courtyard
   out of colored primitives, with a five-second camera push-in and a matching prompt. Press
   **Numpad 0** to look through the camera.
2. **Go Live.** That one button captures your camera view as the reference, connects to
   Reactor (assigning a GPU can take a little while; the panel shows progress), creates the
   world, and splits your viewport to show the output next to your scene.
3. Move the camera, scrub the timeline, or edit the prompt. The world follows, about a second
   behind.

**Pause** holds the world. **Stop** ends the session, which also stops billing. Sessions end on
their own after an hour.

> **Tip:** the first world you make from a raw capture will look a lot like your cubes. That's
> expected. See [Getting a good look](#getting-a-good-look) for the trick that makes it sing.

## Getting a good look

EdenLive takes two things from you: a **reference image** that says *what it should look
like*, and a **prompt** that says *what it is*. Your scene and camera do the rest.

**The reference image is the big lever.** The model matches its style closely, so a plain
viewport capture gives you a plain-looking world. The workflow that works:

1. Click **Capture** to save the camera view (Go Live does this for you the first time; the
   file path is in the *Reference* field).
2. Open that PNG in any image tool with AI editing (Photoshop, Krita with a plugin, a web app
   like Midjourney's editor, ChatGPT...) and restyle it. Keep the camera angle and the object
   positions. For example:
   > Restyle this as a sunlit ancient jungle temple courtyard, cinematic and realistic:
   > weathered stone pillars, mossy steps, a carved golden statue, tropical trees, a turquoise
   > pond. Keep the camera angle, perspective and position of every object.
3. Pick the restyled image as the **Reference** and press **Restart World**.

**Use Output** is the shortcut once you're going: it grabs the latest generated frame as the
new reference, so you can bake in a look you like. Then **Restart World**.

**The prompt** describes the scene in plain language. Edits go live as you type and apply from
the next chunk, so try things like *"...at night, lit by torches and blue moonlight"* while the
world is running. For long prompts, pick a Text datablock in the *Text* field and press
**Send** when you've edited it.

**Build scenes the model can read.** Give every object its own flat color and a clear
silhouette. Use Solid shading with *Object* color. Keep text, grids and gizmos out of the frame
(the add-on hides overlays for you). Smooth camera moves work better than fast cuts. The model
sees 1280×704; the demo scene is set to exactly that.

## Recording a shot

**Record Timeline** plays your scene's frame range through EdenLive and saves MP4s. It's slower than real time because it first draws every frame, then streams them at a
steady rate, then lines the returned frames back up with your timeline so every generated frame
lands on the right frame number.

It uses the scene's frame range. Under *Record Settings* you can change the range, the
**Output** folder (empty means an `eden_live_renders` folder next to your .blend file) and the
**Take** name. Press **Esc** to cancel. You don't need to be live first; Record connects on its
own.

You get:

| File | What's in it |
|---|---|
| `<take>_main.mp4` | The generated shot, one frame per timeline frame, at your scene's fps. |
| `<take>_side_by_side.mp4` | Your draft on the left, the generated frame on the right. Great for showing clients. |
| `<take>_raw.mp4` | Everything the model sent back, unaligned. |
| `<take>_report.json` | Frame counts, latency, prompt, seed. |

Encoding uses Blender's built-in FFmpeg, so there's nothing to install. If encoding ever
fails, the PNG frames are kept and **Open Frames Folder** appears in the panel.

## The panel

<img src="docs/media/panel_live.png" alt="The EdenLive sidebar while live" width="340" align="right">

| Section | What's there |
|---|---|
| **Reference** | The look. **Capture** saves the camera view; **Use Output** saves the latest generated frame. |
| **Prompt** | What the scene is. Edits go live as you type. Pick a Text datablock instead for long prompts, and press **Send**. |
| **Camera / Viewport** | What EdenLive sees: the scene camera (what you'd render) or whatever your viewport shows (fly around freely). |
| **Go Live** | Captures a reference if you have none, connects, starts the world, opens the preview. While live it becomes a status line with **Pause** / **Stop** and **Restart World** (apply a new reference). |
| **Record Timeline** | Plays the frame range through EdenLive and saves MP4s. Shows progress while it runs and where the files went when done. |
| **Record Settings** (collapsed) | Frame range, output folder, take name. |
| **Advanced** (collapsed) | *Seed* (same seed + reference + draft repeats a world). *Stream FPS* (10-60, default 20). *Draft side by side* in the preview. *Hide overlays*. *Draft render*: viewport (fast) or the scene's render engine. *Keep PNG frames*. |
| **Log** (collapsed) | Frame rates and the last few messages from the session. |

The ⌄ menu in the panel header has **Preview: Split Viewport** / **New Window** (for a second
monitor), **Build Demo Scene**, **Open Output Folder**, **Preferences** and **Get a Reactor API
Key**. The live preview is an ordinary Blender image called **EdenLive Preview**, so you can also
show it in any Image Editor.

## Cost and privacy

- EdenLive is billed per minute of session time while you're connected. **Stop** ends it.
  Sessions are capped at 60 minutes so a forgotten one can't run up a bill; press **Go Live**
  again to continue. See [Reactor billing](https://docs.reactor.inc/resources/billing).
- Your API key is stored in Blender's user preferences, never in `.blend` files, so scenes are
  safe to share. The add-on never logs the key.
- What leaves your machine: the draft frames you stream, the reference image and the prompt.

## Troubleshooting

| What you see | What to do |
|---|---|
| "Online access is disabled" | Edit > Preferences > System > Network > **Allow Online Access**. |
| "Reactor SDK not available" | Install the zip from the [Releases page](https://github.com/willemhelmet/Eden-live-blender-reactor/releases/latest) rather than a git checkout. On Linux the SDK needs glibc 2.34+ (Ubuntu 22.04 or newer). |
| "401 Invalid API key" | Re-copy the `rk_...` key from the dashboard and check for stray spaces. |
| Status stays at *connecting (waiting)* | Reactor is assigning a GPU. This can take a while when busy. The **Log** section shows progress. |
| *image_required* / *prompt_required* | Pick a reference image / write a prompt, then **Restart World**. |
| The output looks like my cubes | Your reference is a raw capture. Restyle it: [Getting a good look](#getting-a-good-look). |
| The output lags about a second | Expected. Recording compensates for it; the live preview can't. |
| "Draft capture 1 fps" in the panel | Your viewport is slow to draw (heavy scene, Rendered shading, software OpenGL). Switch to Solid shading. The stream rate stays steady regardless. |
| "The 3D Viewport did not redraw" | Keep a 3D Viewport visible (not minimized) while streaming or recording, or set *Draft render* to *Render engine* under Advanced. |
| Black preview | Wait for the status line to say *running*. Until a world exists, EdenLive shows the staged reference, or black. |
| MP4 not written | The PNG frames are kept. Use **Open Frames Folder**, or check `<take>_work/encode.log`. |
| "Connection to Reactor closed (sessions end after 60 minutes)" | Press **Go Live** again. |

Still stuck? [Open an issue](https://github.com/willemhelmet/Eden-live-blender-reactor/issues)
with the contents of the **Log** section.

## For developers

Architecture, build and release process, tests, and the offline mock backend are in
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## License

MIT, see [LICENSE](LICENSE). The zip bundles the
[Reactor Python SDK](https://pypi.org/project/reactor-sdk/) (Apache-2.0). EdenLive is a hosted
model by VAST on Reactor; using it is subject to Reactor's terms.
