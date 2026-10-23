import os

import bpy

from . import deps, live
from .operators import DASHBOARD_URL, HELP_URL, resolve_path
from .prefs import get_api_key, get_prefs, use_mock
from .session import get_session


class EdenLivePanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "EdenLive"


class EDENLIVE_MT_main(bpy.types.Menu):
    bl_label = "EdenLive"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.eden_live
        layout.operator("eden_live.open_preview", text="Preview: Split Viewport", icon="SPLIT_VERTICAL").target = "SPLIT"
        layout.operator("eden_live.open_preview", text="Preview: New Window", icon="WINDOW").target = "WINDOW"
        layout.separator()
        layout.operator("eden_live.build_demo", icon="MESH_CUBE")
        out_dir = resolve_path(settings.record_dir or "//eden_live_renders/")
        if os.path.isdir(out_dir):
            layout.operator("wm.path_open", text="Open Output Folder", icon="FILE_FOLDER").filepath = out_dir
        layout.separator()
        layout.operator("eden_live.open_preferences", text="Preferences (API Key)", icon="PREFERENCES")
        layout.operator("wm.url_open", text="Get a Reactor API Key", icon="URL").url = DASHBOARD_URL
        layout.operator("wm.url_open", text="Help", icon="HELP").url = HELP_URL


def draw_setup(layout, prefs):
    """First run: nothing but the key field and where to get one."""
    box = layout.box()
    col = box.column(align=True)
    col.label(text="Paste your Reactor API key to start", icon="KEYINGSET")
    if prefs is not None:
        col.prop(prefs, "api_key", text="")
    col.label(text="reactor.inc > your user icon > API Keys")
    row = box.row(align=True)
    row.operator("wm.url_open", text="Get a Key", icon="URL").url = DASHBOARD_URL
    row.operator("eden_live.open_preferences", text="Preferences", icon="PREFERENCES")


def draw_sdk_missing(layout, detail):
    box = layout.box()
    col = box.column(align=True)
    col.label(text="Reactor SDK not installed", icon="ERROR")
    col.label(text="Install the zip from the Releases page,")
    col.label(text="or install the SDK from the preferences.")
    box.operator("eden_live.open_preferences", text="Preferences", icon="PREFERENCES")


def draw_look(layout, settings):
    col = layout.column(align=True)
    col.label(text="Reference", icon="IMAGE_REFERENCE")
    col.prop(settings, "reference_path", text="")
    row = col.row(align=True)
    row.operator("eden_live.capture_reference", icon="RESTRICT_RENDER_OFF")
    row.operator("eden_live.reference_from_output", icon="IMAGE_DATA")

    col = layout.column(align=True)
    col.label(text="Prompt", icon="SMALL_CAPS")
    if settings.prompt_text is None:
        col.prop(settings, "prompt", text="")
    row = col.row(align=True)
    row.prop(settings, "prompt_text", text="")
    if settings.prompt_text is not None:
        row.operator("eden_live.send_prompt", text="Send", icon="EXPORT")

    row = layout.row(align=True)
    row.prop(settings, "source_mode", expand=True)


def draw_go_live(layout, session):
    st = session.state
    status = session.status
    go = live.state.go_live
    col = layout.column(align=True)
    if go is not None:
        col.label(text=go.message, icon="SORTTIME")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("eden_live.disconnect", text="Cancel", icon="CANCEL")
    elif status == "ready" and st.get("started"):
        paused = st.get("paused", False)
        col.label(
            text=f"Live: {'paused' if paused else 'running'}, {session.in_meter.rate():.0f} fps out, "
            f"{session.out_meter.rate():.0f} fps back",
            icon="PAUSE" if paused else "RADIOBUT_ON",
        )
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("eden_live.pause", text="Resume" if paused else "Pause", icon="PLAY" if paused else "PAUSE")
        row.operator("eden_live.disconnect", text="Stop", icon="SNAP_FACE")
        col.operator("eden_live.start", text="Restart World", icon="FILE_REFRESH")
    elif status == "ready":
        col.label(text="Connected, no world yet", icon="LINKED")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("eden_live.go_live", icon="PLAY")
        row.operator("eden_live.disconnect", text="Stop", icon="SNAP_FACE")
    elif status in ("connecting", "disconnecting"):
        detail = f" ({session.remote_status})" if status == "connecting" and session.remote_status else ""
        col.label(text=f"{status.capitalize()}{detail}...", icon="SORTTIME")
        row = col.row(align=True)
        row.scale_y = 1.4
        row.operator("eden_live.disconnect", text="Cancel", icon="CANCEL")
    else:
        row = col.row(align=True)
        row.scale_y = 1.6
        row.operator("eden_live.go_live", icon="PLAY")
    if session.last_error:
        layout.label(text=session.last_error, icon="ERROR")
    if live.state.capture_error:
        layout.label(text=live.state.capture_error, icon="ERROR")


def draw_record(layout):
    rec = live.state.recorder
    if rec is not None:
        layout.progress(factor=rec.progress, type="BAR", text=rec.message)
        layout.label(text="Esc cancels", icon="EVENT_ESC")
        return
    row = layout.row()
    row.scale_y = 1.2
    row.operator("eden_live.record", icon="REC")
    last = live.state.last_recorder
    if last is None:
        return
    col = layout.column(align=True)
    col.label(text=last.message, icon="CHECKMARK" if last.phase == "DONE" else "INFO")
    if last.kept_frames:
        col.operator("wm.path_open", text="Open Frames Folder", icon="FILE_FOLDER").filepath = last.kept_frames
    elif last.phase == "DONE":
        col.operator("wm.path_open", text="Open Output Folder", icon="FILE_FOLDER").filepath = last.out_dir


class EDENLIVE_PT_main(EdenLivePanel, bpy.types.Panel):
    bl_label = "EdenLive"

    def draw_header_preset(self, context):
        self.layout.menu("EDENLIVE_MT_main", icon="DOWNARROW_HLT", text="")

    def draw(self, context):
        layout = self.layout
        session = get_session()
        settings = context.scene.eden_live
        if not use_mock():
            ok, detail = deps.sdk_status()
            if not ok:
                draw_sdk_missing(layout, detail)
                return
            if not get_api_key(context):
                draw_setup(layout, get_prefs(context))
                return
        draw_look(layout, settings)
        layout.separator()
        draw_go_live(layout, session)
        layout.separator()
        draw_record(layout)


class EDENLIVE_PT_record(EdenLivePanel, bpy.types.Panel):
    bl_label = "Record Settings"
    bl_parent_id = "EDENLIVE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.eden_live
        scene = context.scene
        col = layout.column(align=True)
        col.prop(scene, "frame_start", text="Frame Start")
        col.prop(scene, "frame_end", text="End")
        col = layout.column()
        col.prop(settings, "record_dir")
        col.prop(settings, "record_name")


class EDENLIVE_PT_advanced(EdenLivePanel, bpy.types.Panel):
    bl_label = "Advanced"
    bl_parent_id = "EDENLIVE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.eden_live
        col = layout.column()
        col.prop(settings, "seed")
        col.prop(settings, "fps")
        col.prop(settings, "show_draft")
        col.prop(settings, "hide_overlays")
        layout.separator()
        col = layout.column()
        col.prop(settings, "record_method")
        col.prop(settings, "record_keep_frames")


class EDENLIVE_PT_log(EdenLivePanel, bpy.types.Panel):
    bl_label = "Log"
    bl_parent_id = "EDENLIVE_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        session = get_session()
        col = self.layout.column(align=True)
        if session.status == "ready":
            st = session.state
            world = f"#{st.get('world_id')}" if st.get("started") else "none"
            col.label(text=f"{session.backend_label}: world {world}, {st.get('chunks', 0)} chunks", icon="INFO")
            col.label(text=f"Sending {session.in_meter.rate():.0f} fps, receiving {session.out_meter.rate():.0f} fps")
            col.label(text=f"Draft capture {live.state.capture_meter.rate():.0f} fps "
                      f"({live.state.capture_cost * 1000:.0f} ms each)")
            col.separator()
        for line in list(session.log)[-12:]:
            col.label(text=line)


classes = (EDENLIVE_MT_main, EDENLIVE_PT_main, EDENLIVE_PT_record, EDENLIVE_PT_advanced, EDENLIVE_PT_log)
