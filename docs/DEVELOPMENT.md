# Development

This page is for people working on the add-on. If you just want to use it, start with the
[README](../README.md).

## Contents

- [Repository layout](#repository-layout)
- [Build the zip](#build-the-zip)
- [Releases](#releases)
- [Tests](#tests)
- [Developer environment variables](#developer-environment-variables)
- [Architecture](#architecture)
- [EdenLive protocol](#edenlive-protocol)
- [Code map](#code-map)
- [Legacy add-on install](#legacy-add-on-install)

## Repository layout

```
eden_live_previs/            the add-on (extension root, blender_manifest.toml)
examples/build_demo_scene.py build/save the demo scene headlessly
tools/build_extension.py     fetch wheels and build the extension zip
tests/test_headless.py       blender -b: unit tests + mock session + record -> MP4 (CI)
tests/test_ui.py             needs a display: drives the real UI end to end (mock by default)
tests/test_live_reactor.py   real reactor/eden-live session (needs REACTOR_API_KEY; billed)
docs/                        this page and media for the README
.github/workflows/ci.yml     tests + build on every push and PR (Blender 4.2 and 5.2)
.github/workflows/release.yml builds and publishes a GitHub Release when a v* tag is pushed
```

## Build the zip

```bash
python3 tools/build_extension.py --blender /path/to/blender
# -> dist/eden_live_previs-<version>.zip
```

The script downloads the four `reactor-sdk` wheels pinned in `blender_manifest.toml` from
PyPI, verifies their SHA-256, then runs Blender's `extension build` and `extension validate`.

**One zip for every platform.** The zip carries all four wheels (Windows x64, macOS arm64,
macOS x64, Linux x64; about 10 MB each). Blender's extension system reads the wheel filename
tags and installs only the one that matches the machine, so a single download works everywhere.
`blender_manifest.toml` lists the wheels and the `platforms` they cover.

`--legacy` also writes `eden_live_previs-<version>-legacy-addon.zip` (no wheels), see
[Legacy add-on install](#legacy-add-on-install). `--skip-blender` only fetches wheels.

To bump the SDK: change the four wheel filenames and `SDK_REQUIREMENT` in `deps.py`, then
rebuild. The build fails if a wheel is not on PyPI.

## Releases

Releases are built and published by `.github/workflows/release.yml` when a tag is pushed:

```bash
# 1. set version = "x.y.z" in eden_live_previs/blender_manifest.toml and (0, x, y) in __init__.py
# 2. merge to main, then:
git tag vx.y.z
git push origin vx.y.z
```

The workflow checks that the tag matches the manifest version, builds the zip on Blender
4.2.3, and creates a GitHub Release named `EdenLive Pre-vis vx.y.z` with the zip attached and
auto-generated notes. It appears under **Releases** on the repository page within about five
minutes. CI also uploads the zip as a workflow artifact on every push, for testing branches.

## Tests

```bash
blender -b --factory-startup --python tests/test_headless.py      # 12 checks, ~2 min
blender --python tests/test_ui.py                                  # opens Blender, quits when done
REACTOR_API_KEY=rk_... blender -b --factory-startup --python tests/test_live_reactor.py
```

`test_headless.py` runs unit tests, a full mock session, and a record to MP4 without a display.
`test_ui.py` drives the real panel and operators with the mock backend. `test_live_reactor.py`
connects to the real model, saves its runtime schema to `schema.json`, checks the tracks and
commands this add-on relies on, records 48 demo frames through EdenLive and writes the MP4s and
report. Set `EDEN_REFERENCE=/path/to/restyled.png` for nicer output. It is billed.

CI runs the headless tests and the build on Blender 4.2.3 and 5.2.3 (Linux, software OpenGL),
then installs the zip and imports the bundled SDK.

## Developer environment variables

Not exposed in the UI.

| Variable | Effect |
|---|---|
| `EDEN_LIVE_MOCK=1` | Use the offline mock backend instead of Reactor: repaints the draft with the reference's palette after ~1 s, following EdenLive's commands, refusal codes and tracks. Handy for UI work without a key or billing. |
| `REACTOR_API_URL` | Override the Reactor API base URL (default `https://api.reactor.inc`; normalized: `https://` added, trailing `/` removed). |
| `REACTOR_API_KEY` | Used when the API key preference is empty. |

## Architecture

```
 Blender main thread                         background threads (no bpy)
 ───────────────────                         ───────────────────────────
 bpy timer (60 Hz) ── request draft ──┐      EdenLiveSender ── push_frame @ fixed fps ──► source_video
 3D Viewport draw callback ◄──────────┘        (repeats newest frame, stamps scheduled time)
   GPUOffScreen.draw_view3d(camera) ── frame ─► session.source
 Record modal operator ── pre-rendered drafts (memmap) ─► PlaylistProvider ─┘
                                             EdenLiveLoop (asyncio) ── reactor_sdk.Reactor
                                               connect / upload_file / send_command
 Preview Image  ◄── foreach_set ◄── EdenLivePreview ◄── main_video / draft_video (SDK thread)
 Sidebar panel  ◄── polls session.state ◄── state_update messages
                                             EdenLiveWriter ── PNG frames ─► align ─► MP4
```

**In-process SDK with bundled wheels, not a sidecar.** The Reactor Python SDK (`reactor-sdk`)
is pure Python over a prebuilt native library (Rust + libwebrtc). It has no Python
dependencies, ships `py3-none` wheels for every desktop platform Blender supports, and runs on
Blender's bundled Python 3.11 and 3.13. Blender 4.2's extension format is built for exactly
this: list the wheels in `blender_manifest.toml` and Blender installs the matching one itself.
There is no runtime pip, no compiler and no second Python install. A sidecar process would add
a second interpreter to ship, an IPC protocol for 30 MB/s of frames, and process-lifecycle
failure modes, all to solve a problem we don't have. The **Install Reactor SDK** button in the
preferences (Blender's own `python -m pip --target <user dir>`) is the fallback for git
checkouts and the legacy add-on zip. aiortc/PyAV aren't needed: the SDK does the WebRTC itself.

**Never blocking the UI.** Networking, commands and uploads run on a private asyncio loop
thread. Frame pushes run on a dedicated sender thread at a fixed rate. Frame conversion for
the preview and PNG writing run on their own threads. The main thread only captures (a few ms
on a GPU), copies preview pixels into an Image, and draws the panel.

**Steady frame rate.** EdenLive wants steady 10-60 fps, and its output plays at the rate frames
arrive. The sender thread pushes the newest captured frame on a fixed schedule, repeating it if
Blender is busy, and stamps each frame with its *scheduled* time through the SDK's
`capture_time_us`. So even when the main thread holds Python's GIL for a moment, the model sees
evenly spaced frames. If capture is slow (heavy scene, no GPU), live capture backs off so the
stream rate holds. Recording goes further: drafts are rendered first, then streamed from memory
on an exact schedule, so render speed never affects timing.

**Capture inside the viewport's draw callback.** Drafts are drawn with
`GPUOffScreen.draw_view3d` from a `SpaceView3D` draw handler, using the camera's own projection
for 1280×704. Drawing from a timer instead uses whatever window's GPU context is current, and
renders black once another window, such as the preview, has drawn. Background mode (`-b`)
renders with the scene's engine instead.

**Recording pipeline.** Record works in three stages. (1) Render drafts: each frame of the
frame range is drawn from the active camera at 1280×704, with the viewport's shading or the
scene's render engine. (2) Stream: a fresh world is started, the first frame is held until
EdenLive returns its first chunk, then the frames play at exactly the scene's fps (clamped to
10-60), and the last frame is held for a tail of a few seconds to collect delayed output.
Returned frames are written to disk as they arrive. (3) Align and encode: returned
`draft_video` frames are matched back to the frames that were sent (frame tags when the model
echoes them, otherwise thumbnail matching plus the measured latency), so each generated frame
lands on its timeline frame. Encoding uses Blender's own FFmpeg (H.264 through a temporary
Video Sequencer scene) in a separate background Blender process; if that process can't run, the
add-on encodes in the current Blender. If encoding fails, the PNG sequences are kept
(`<take>_work/seq/{main,draft,raw}`) and `<take>_work/encode.log` holds the encoder output.

**Secrets.** The API key lives in Blender's user preferences (`userpref.blend`), never in
`.blend` scene files. The session scrubs it from log and error text. The SDK exchanges it for a
short-lived session token on connect, so the key only goes to `api.reactor.inc/tokens`.

**Session cap.** Sessions are disconnected after 60 minutes so a forgotten session can't run up
a bill.

## EdenLive protocol

Per the [schema](https://docs.reactor.inc/model-api-reference/eden-live/schema): connect,
publish `source_video`, `set_source({source: "client"})`; on Start, `set_paused(true)` if a
world is playing, `upload_file` the reference, `set_image`, `set_prompt`, `start({seed})`;
`set_prompt` for live edits; `set_paused` for pause and resume; `state_update` snapshots drive
the panel; the session is disconnected on Stop or quit.

## Code map

`eden_live_previs/`:

| Module | Role |
|---|---|
| `session.py` | Threads, frame slots, command sequences, error reporting. No bpy. |
| `backends.py` | `ReactorBackend` (reactor-sdk) and `MockBackend` (offline stand-in emulating EdenLive's commands, refusal codes, latency and tracks). API URL handling. |
| `capture.py` | Draw-callback viewport capture, render-engine capture, image I/O. |
| `live.py` | Main-thread timer: capture scheduling, prompt debounce, preview image, redraws. |
| `recorder.py`, `align.py`, `encode.py` | Record pipeline, frame alignment, MP4 encoding. |
| `imaging.py` | Resize/cover helpers at EdenLive's 1280×704. |
| `operators.py`, `ui.py`, `props.py`, `prefs.py` | Blender UI. |
| `deps.py` | Finds the SDK; the legacy pip fallback. |
| `demo.py` | The primitive demo scene. |

## Legacy add-on install

For a git checkout, or the `--legacy` zip, there are no wheels. Install or link the
`eden_live_previs/` folder as a legacy add-on, enable it, then open the add-on's preferences and
click **Install Reactor SDK**. That runs Blender's own Python
`-m pip install --target <extension user dir> reactor-sdk` in the background. It needs online
access, and you only do it once.

## License

MIT, see [LICENSE](../LICENSE). The extension zip bundles the
[Reactor Python SDK](https://pypi.org/project/reactor-sdk/) wheels, which are Apache-2.0
licensed and carry their own license file. EdenLive is a hosted model by VAST on Reactor; using
it is subject to Reactor's terms.
