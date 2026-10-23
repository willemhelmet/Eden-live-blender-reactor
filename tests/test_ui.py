"""Interactive smoke test: drives the real UI (needs a display, not -b).

    blender --python tests/test_ui.py                 # add-on from this checkout, mock backend (EDEN_LIVE_MOCK)
    EDEN_BACKEND=REACTOR REACTOR_API_KEY=rk_... blender --python tests/test_ui.py

Builds the demo scene, opens the EdenLive sidebar, presses Go Live (which captures a
reference, connects, starts a world and opens the split preview on its own), checks
the preview, edits the prompt live, pauses and resumes, records the timeline (first
48 frames) through the modal operator, then quits. Prints PASS/FAIL lines and exits
non-zero on failure. Set EDEN_KEEP_OPEN=1 to leave Blender running afterwards, EDEN_SHOT=/path.png
to save a screenshot of the window while live.
"""

import os
import sys
import time
import traceback

import addon_utils
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT = "bl_ext.user_default.eden_live_previs"


def enable_addon():
    if EXT in bpy.context.preferences.addons:
        return EXT
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    addon_utils.enable("eden_live_previs", default_set=True)
    return "eden_live_previs"


bpy.context.preferences.view.show_splash = False  # keep the splash out of screenshots
MODULE = enable_addon()
pkg = sys.modules[MODULE]
session_mod = sys.modules[MODULE + ".session"]
live = sys.modules[MODULE + ".live"]
failures = []


def log(msg):
    session = session_mod.get_session()
    src, _ = session.source.get()
    main, _ = session.main.get()
    means = [f"{float(a[..., :3].mean()):.0f}" if a is not None else "-" for a in (src, main)]
    print(f"{msg}  [source/main mean {means[0]}/{means[1]}]")
    sys.stdout.flush()


def window_ctx():
    window = bpy.context.window_manager.windows[0]
    area = max((a for a in window.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == "WINDOW")
    return dict(window=window, area=area, region=region, screen=window.screen)


def wait(pred, timeout, what):
    deadline = time.perf_counter() + timeout
    while not pred():
        if time.perf_counter() > deadline:
            raise AssertionError(f"timeout: {what}")
        yield 0.1


def steps():
    if os.environ.get("EDEN_BACKEND") != "REACTOR":
        os.environ["EDEN_LIVE_MOCK"] = "1"
    session = session_mod.get_session()
    ctx = window_ctx()

    with bpy.context.temp_override(**ctx):
        bpy.ops.eden_live.build_demo()
    yield 0.5
    ctx = window_ctx()
    space = ctx["area"].spaces.active
    space.show_region_ui = True
    with bpy.context.temp_override(**ctx):
        bpy.ops.view3d.view_camera()
    scene = bpy.context.scene
    scene.frame_end = 48
    yield 0.5
    for region in ctx["area"].regions:
        if region.type == "UI":
            try:
                region.active_panel_category = "EdenLive"
            except Exception:
                pass
    yield 0.5

    if os.environ.get("EDEN_SHOT_PAUSE"):
        yield float(os.environ["EDEN_SHOT_PAUSE"])
    scene.eden_live.reference_path = ""
    with bpy.context.temp_override(**ctx):
        assert bpy.ops.eden_live.go_live() == {"FINISHED"}
    assert live.state.go_live is not None
    yield from wait(lambda: scene.eden_live.reference_path, 10, "reference auto-capture")
    ref = bpy.path.abspath(scene.eden_live.reference_path)
    assert os.path.isfile(ref), ref
    log(f"PASS Go Live captured a reference: {ref}")
    yield from wait(lambda: session.status in ("ready", "error"), 180, "connect")
    assert session.ready, session.last_error
    log(f"PASS Go Live connected ({session.backend_label})")
    yield from wait(lambda: live.state.go_live is None, 30, "go-live sequence")
    assert not session.last_error, session.last_error
    yield from wait(lambda: session.state.get("started") and session.main.seq > 5, 120, "first frames")
    yield 3.0
    rate = session.in_meter.rate()
    assert rate >= 0.75 * scene.eden_live.fps, f"sending only {rate:.1f} fps"
    log(f"PASS Go Live started the world; sending {rate:.1f} fps (target {scene.eden_live.fps}), draft capture "
        f"{live.state.capture_meter.rate():.1f} fps at {live.state.capture_cost * 1000:.0f} ms each")

    ctx = window_ctx()
    editors = [a for a in ctx["window"].screen.areas if a.type == "IMAGE_EDITOR"]
    assert editors and editors[0].spaces.active.image.name == live.PREVIEW_IMAGE
    log("PASS Go Live opened the preview split next to the 3D Viewport")
    scene.eden_live.show_draft = True
    yield 2.0
    image = bpy.data.images.get(live.PREVIEW_IMAGE)
    assert image is not None and tuple(image.size) == (2560, 704), image and tuple(image.size)
    import numpy as np

    pixels = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(pixels)
    halves = pixels.reshape(704, 2560, 4)[..., :3]
    left, right = float(halves[:, :1280].mean()), float(halves[:, 1280:].mean())
    assert left > 0.05 and right > 0.05, (left, right)
    source, _ = session.source.get()
    assert float(source[..., :3].mean()) > 5, "captured drafts went black after opening the preview window"
    log(f"preview pixel means: draft {left:.3f}, main {right:.3f}")
    log(f"PASS preview image updating ({tuple(image.size)}), receiving {session.out_meter.rate():.0f} fps")
    if os.environ.get("EDEN_SHOT_PAUSE"):
        yield float(os.environ["EDEN_SHOT_PAUSE"])
    if os.environ.get("EDEN_SHOT"):
        # EDEN_SHOT=/path/to.png saves a screenshot of the Blender window while live.
        ctx = window_ctx()
        for region in ctx["area"].regions:
            if region.type == "UI":
                region.active_panel_category = "EdenLive"
        yield 0.5
        with bpy.context.temp_override(**ctx):
            bpy.ops.screen.screenshot(filepath=os.environ["EDEN_SHOT"])
        log(f"screenshot saved to {os.environ['EDEN_SHOT']}")

    scene.eden_live.prompt = "The same temple courtyard at night, lit by torches and blue moonlight."
    yield from wait(lambda: "night" in session.state.get("prompt", ""), 10, "live prompt")
    log("PASS live prompt edit sent")

    with bpy.context.temp_override(**ctx):
        bpy.ops.eden_live.pause()
    yield from wait(lambda: session.state.get("paused"), 10, "pause")
    with bpy.context.temp_override(**ctx):
        bpy.ops.eden_live.pause()
    yield from wait(lambda: not session.state.get("paused"), 10, "resume")
    log("PASS pause / resume")
    yield 2.0

    with bpy.context.temp_override(**ctx):
        bpy.ops.eden_live.record("INVOKE_DEFAULT")
    yield 0.5
    yield from wait(lambda: live.state.recorder is None, 600, "recording")
    rec = live.state.last_recorder
    assert rec is not None and rec.phase == "DONE", rec and rec.message
    for key in ("main", "side_by_side", "raw"):
        assert os.path.getsize(rec.outputs[key]) > 10000
    log(f"PASS recorded: {rec.outputs['main']} report={rec.report}")

    with bpy.context.temp_override(**ctx):
        bpy.ops.eden_live.disconnect()
    yield from wait(lambda: session.status == "disconnected", 15, "disconnect")
    assert not session.last_error, session.last_error
    log("PASS stopped")


_gen = steps()


def driver():
    try:
        return next(_gen)
    except StopIteration:
        log("UI TEST DONE: " + ("FAIL" if failures else "ALL PASS"))
    except Exception:
        failures.append(traceback.format_exc())
        log("FAIL\n" + failures[-1])
    if not os.environ.get("EDEN_KEEP_OPEN"):
        bpy.app.timers.register(lambda: os._exit(1 if failures else 0), first_interval=1.0)
    return None


bpy.app.timers.register(driver, first_interval=2.0)
