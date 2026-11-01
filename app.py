"""BoliCAD — multilingual voice to deterministic, editable 3D solids."""
from __future__ import annotations

import hashlib
import html
import json

import streamlit as st
from pydantic import ValidationError

from ai_service import LANGUAGES, ServiceError, load_key, make_client, transcribe, understand
from cad_schema import DEFAULTS, TITLES, ShapeSpec, default_spec, validation_message
from geometry import build_mesh, export_stl
from viewer import figure

st.set_page_config(page_title="BoliCAD · From voice to 3D", page_icon="⬡", layout="wide", initial_sidebar_state="collapsed")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;550;600;650;700;750;800&display=swap');
:root {font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#111;}
html,body,[class*="css"],.stApp {font-family:Inter,ui-sans-serif,system-ui,sans-serif;}
.stApp {background:#fff;}
[data-testid="stHeader"] {background:transparent;height:0;}
[data-testid="stToolbar"] {visibility:hidden;}
.block-container {max-width:1510px;padding:2.3rem 3.4rem 1.4rem;}
h1,h2,h3,p {color:#111;letter-spacing:-.035em;}
h1 {font-size:2.7rem!important;font-weight:650!important;line-height:1.13!important;margin:0 0 .7rem!important;padding:0!important;}
h3 {font-size:1rem!important;font-weight:600!important;}
p {letter-spacing:-.015em;}
.brand {display:flex;align-items:center;gap:11px;font-size:25px;font-weight:700;letter-spacing:-1.2px;}
.brand svg {width:30px;height:30px;}
.brandline {font-size:12px;color:#777;letter-spacing:0;margin-top:6px;}
.topbar {display:flex;align-items:center;justify-content:space-between;padding-bottom:26px;border-bottom:1px solid #e5e5e5;margin-bottom:35px;gap:15px;}
.topright {font-size:11px;color:#6e6e6e;text-align:right;line-height:1.9;letter-spacing:.02em;}
.badge {display:inline-block;padding:4px 9px;border:1px solid #dedede;border-radius:4px;font-size:10px;font-weight:550;color:#555;background:white;letter-spacing:.04em;}
.eyebrow {font-size:10px;color:#888;font-weight:600;letter-spacing:.13em;margin:0 0 16px;}
.lede {font-size:14px;line-height:1.7;color:#777;max-width:340px;margin:0 0 18px;letter-spacing:-.015em;}
.small-label {font-size:10px;font-weight:600;color:#888;letter-spacing:.12em;margin:15px 0 9px;}
.workspace-title {display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;gap:12px;}
.workspace-title strong {font-size:14px;font-weight:550;letter-spacing:-.025em;}
.workspace-title span {font-size:10px;color:#888;letter-spacing:.06em;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:6px!important;}
[data-testid="stVerticalBlock"] {gap:.8rem;}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button,[data-testid="stFormSubmitButton"] button {min-height:43px;border-radius:5px;font-weight:500;font-size:12px;border-color:#dedede;box-shadow:none;}
[data-testid="stButton"] button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"],[data-testid="stDownloadButton"] button[kind="primary"] {background:#111;border-color:#111;color:#fff;}
[data-testid="stButton"] button p,[data-testid="stFormSubmitButton"] button p,[data-testid="stDownloadButton"] button p {color:inherit;}
[data-testid="stButton"] button:hover {border-color:#111;color:#111;}
[data-testid="stButton"] button[kind="primary"]:hover {background:#333;color:#fff;}
[data-testid="stTextArea"] textarea {font-size:13px;line-height:1.65;border-radius:5px;background:#fafafa;}
[data-testid="stWidgetLabel"] p {font-size:11px;font-weight:500;color:#555;letter-spacing:0;}
[data-testid="stCaptionContainer"] p {font-size:11px;line-height:1.65;color:#888;letter-spacing:0;}
[data-testid="stAudioInput"] {width:100%;}
[data-testid="stAudioInput"] button {min-width:52px;min-height:52px;}
[data-testid="stAudioInput"] button[aria-label="Record"] {border-radius:50%;background:#111;color:#fff;}
.viewer-caption {display:flex;justify-content:space-between;font-size:10px;color:#999;margin:1px 2px 0;letter-spacing:.03em;}
.part-name {font-size:20px;font-weight:550;letter-spacing:-.04em;margin:12px 0 4px;}
.part-detail {font-size:11px;color:#888;letter-spacing:0;}
.stats {display:grid;grid-template-columns:repeat(3,1fr);margin:21px 0 19px;border-top:1px solid #e5e5e5;border-bottom:1px solid #e5e5e5;}
.stat {padding:15px 5px 15px 0;}
.stat + .stat {padding-left:20px;border-left:1px solid #e5e5e5;}
.stat-label {font-size:9px;color:#888;letter-spacing:.09em;text-transform:uppercase;margin-bottom:7px;}
.stat-value {font-size:16px;letter-spacing:-.04em;font-weight:500;white-space:nowrap;}
.stat-value small {font-size:10px;color:#999;font-weight:400;}
.foot {display:flex;justify-content:space-between;gap:12px;border-top:1px solid #e5e5e5;padding-top:19px;margin-top:34px;font-size:10px;color:#999;letter-spacing:.01em;}
[data-testid="stExpander"] {border-radius:5px;border-color:#e5e5e5;}
[data-testid="stExpander"] summary p {font-size:12px;}
[data-testid="stAlert"] {border-radius:5px;font-size:12px;}
@media(min-width:850px) {[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stMarkdownContainer"] .eyebrow) {gap:3.5rem;}}
@media(max-width:850px) {.block-container{padding:1.3rem 1.1rem;}h1{font-size:2.2rem!important;}.topbar{margin-bottom:25px;}.topright{font-size:9px;}.brandline{font-size:10px;}.foot{font-size:9px;}.stats{margin-top:15px;}.stat + .stat{padding-left:10px;}.stat-value{font-size:14px;}}
@media(max-width:640px) {[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .eyebrow){flex-direction:column;}[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .eyebrow)>[data-testid="stColumn"]{width:100%!important;flex:1 1 100%!important;}.topright{display:none;}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

if "spec" not in st.session_state:
    st.session_state.spec = default_spec()
    st.session_state.revision = 0
    st.session_state.reset_view = 0
    st.session_state.source = "Starter design · edit dimensions or describe your own"
    st.session_state.prompt = ""
    st.session_state.intent = "Create"

if "next_intent" in st.session_state:
    st.session_state.intent = st.session_state.pop("next_intent")

try:
    secrets = st.secrets.to_dict()
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    secrets = {}
api_key = load_key(secrets)


@st.cache_data(show_spinner=False, max_entries=48, ttl=3600)
def solid(spec_json):
    mesh = build_mesh(ShapeSpec.model_validate_json(spec_json))
    return mesh, export_stl(mesh)


def accept(spec, source):
    solid(spec.model_dump_json())  # Transaction: preserve the old model on any failure.
    st.session_state.spec = spec
    st.session_state.revision += 1
    st.session_state.source = source
    st.session_state.next_intent = "Refine"


def example(text):
    st.session_state.prompt = text
    st.session_state.intent = "Create"


st.markdown('''<div class="topbar"><div><div class="brand"><svg viewBox="0 0 32 32" fill="none" stroke="#111" stroke-width="1.6"><path d="M16 2 29 9.5v13L16 30 3 22.5v-13Z"/><path d="m3 9.5 13 7.5 13-7.5M16 17v13M9.5 5.75l13 7.5v12.9"/></svg>BoliCAD<span class="badge">WORKSPACE</span></div><div class="brandline">Voice-Powered Parametric Design.</div></div><div class="topright">FROM AN IDEA TO A SOLID.<br>YOUR LANGUAGE. YOUR DIMENSIONS.</div></div>''', unsafe_allow_html=True)

left, right = st.columns([.38, .62], gap="large")
with left:
    st.markdown('<div class="eyebrow">01 / DESIGN INPUT</div><h1>Describe it.<br>See it.</h1><p class="lede">Turn a few words into something you can make. Speak your language. Shape every detail.</p>', unsafe_allow_html=True)
    language = st.selectbox("Your language", list(LANGUAGES), format_func=LANGUAGES.get, key="language")
    audio = st.audio_input("Speak your design", sample_rate=16000, help="Record a command under 29 seconds. The recording is processed by Sarvam and kept only in this session.")
    st.caption("Tap to record, then stop. Keep your command under 29 seconds.")
    if audio:
        audio_hash = hashlib.sha256(audio.getvalue() + language.encode()).hexdigest()
        retry = False
        if st.session_state.get("audio_error_hash") == audio_hash:
            retry = st.button("Retry transcription", width="stretch")
        if st.session_state.get("audio_hash") != audio_hash or retry:
            st.session_state.audio_hash = audio_hash
            try:
                with st.spinner("Transcribing your design…"):
                    st.session_state.prompt = transcribe(make_client(api_key), audio.getvalue(), language)
                st.session_state.pop("audio_error_hash", None)
                st.session_state.pop("audio_error", None)
            except ServiceError as exc:
                st.session_state.audio_error_hash = audio_hash
                st.session_state.audio_error = str(exc)
        if st.session_state.get("audio_error_hash") == audio_hash:
            st.warning(st.session_state.audio_error + " You can still type below.")
    st.segmented_control("Design action", ["Create", "Refine"], key="intent", help="Create a new object, or change the current model with a command such as ‘make it 20 mm taller’.")
    st.text_area("Or describe it in writing", key="prompt", height=125, max_chars=4000,
                 placeholder="An 80 mm tall L-bracket, 50 mm wide, with two 5 mm holes…")
    if st.button("Generate Model  →", type="primary", width="stretch"):
        try:
            with st.status("Understanding dimensions…", expanded=True) as status:
                current = st.session_state.spec if st.session_state.intent == "Refine" else None
                new_spec = understand(make_client(api_key), st.session_state.prompt, current)
                status.update(label="Generating model…")
                accept(new_spec, "Generated with Sarvam-105B · validated solid")
                status.update(label="Model ready", state="complete", expanded=False)
            st.rerun()
        except (ServiceError, ValidationError, ValueError) as exc:
            st.error(validation_message(exc))
            st.caption("No changes applied. The workspace still shows your previous valid model.")
    if not api_key:
        st.info("Voice and AI need SARVAM_API_KEY in server secrets. You can build all three shapes with the parameter editor below.")
    st.markdown('<div class="small-label">A STARTING POINT</div>', unsafe_allow_html=True)
    st.button("L-bracket · 80 × 50 × 40 mm", on_click=example,
              args=("Make an L-shaped bracket, height 80 mm, width 50 mm, depth 40 mm, thickness 4 mm, with two 5 mm holes on the upright.",), width="stretch")
    st.button("Mounting plate · four corner holes", on_click=example,
              args=("Create a rectangular mounting plate 100 mm long, 60 mm wide, 4 mm thick, with four 5 mm mounting holes near the corners.",), width="stretch")
    st.button("Open-top box · 3 mm walls", on_click=example,
              args=("Create an open-top box 100 mm long, 70 mm wide and 50 mm high with 3 mm walls and a solid bottom.",), width="stretch")

    st.divider()
    st.markdown("### Make it yours")
    st.caption("Edit any dimension. All values are in millimetres.")
    spec = st.session_state.spec
    family = st.selectbox("Geometry family", list(TITLES), index=list(TITLES).index(spec.shape_type),
                          format_func=TITLES.get, key=f"family_{st.session_state.revision}")
    if family != spec.shape_type:
        accept(default_spec(family), "Parameter design · sensible defaults")
        st.rerun()
    with st.form(f"dimensions_{st.session_state.revision}", border=False):
        edited = {}
        fields = list(DEFAULTS[spec.shape_type])
        for start in range(0, len(fields), 2):
            cells = st.columns(2)
            for cell, name in zip(cells, fields[start:start+2]):
                with cell:
                    value = spec.dimensions[name]
                    label = ("Default hole diameter" if name == "hole_diameter" and spec.hole_layout == "custom" else name.replace("_", " ").capitalize()) + ("" if name == "hole_count" else " (mm)")
                    edited[name] = st.number_input(label, value=int(value) if name == "hole_count" else float(value),
                                                   step=1 if name == "hole_count" else .5,
                                                   format="%d" if name == "hole_count" else "%g", key=f"{name}_{st.session_state.revision}")
        custom = False
        rows = []
        if spec.shape_type != "box":
            custom = st.checkbox("Use custom hole locations", value=spec.hole_layout == "custom")
            with st.expander("Hole locations & diameters", expanded=spec.hole_layout == "custom"):
                st.caption("X runs across the part. Y is depth on the base, or height on the upright. Enable custom locations to apply these values. The table must have exactly ‘Hole count’ rows.")
                st.caption("For custom holes, each table diameter overrides the default hole diameter above.")
                rows = st.data_editor([h.model_dump() for h in spec.holes] or [{"face":"base", "x":10.0,"y":10.0,"diameter":5.0}],
                                      num_rows="dynamic", hide_index=True, width="stretch",
                                      column_config={"face":st.column_config.SelectboxColumn("Face", options=["base", "upright"], required=True),
                                                     "x":st.column_config.NumberColumn("X (mm)",required=True),
                                                     "y":st.column_config.NumberColumn("Y (mm)",required=True),
                                                     "diameter":st.column_config.NumberColumn("Diameter (mm)",required=True)})
        apply = st.form_submit_button("Update geometry", width="stretch")
    if apply:
        try:
            payload = spec.model_dump()
            payload.update(dimensions=edited, hole_layout="custom" if custom else "auto", holes=rows if custom else [],
                           assumptions=["Dimensions explicitly set in the parameter editor."], missing_parameters=[])
            candidate = ShapeSpec.model_validate(payload)
            accept(candidate, "Parameter design · validated solid")
            st.rerun()
        except (ValidationError, ValueError) as exc:
            st.error("Invalid dimensions: " + validation_message(exc))
            st.caption("No changes applied. Correct the values and update again.")

with right:
    spec = st.session_state.spec
    mesh, stl = solid(spec.model_dump_json())
    st.markdown('<div class="eyebrow">02 / 3D WORKSPACE</div><div class="workspace-title"><strong>Every dimension, in your hands.</strong><span class="badge">SOLID / mm</span></div>', unsafe_allow_html=True)
    controls = st.columns([2, 1])
    with controls[0]:
        show_dimensions = st.toggle("Dimension guides", value=True)
    with controls[1]:
        if st.button("Reset view", width="stretch"):
            st.session_state.reset_view += 1
    st.plotly_chart(figure(mesh, show_dimensions, st.session_state.reset_view), width="stretch",
                    config={"displaylogo":False, "scrollZoom":True,
                            "modeBarButtonsToRemove":["toImage", "hoverClosest3d"]}, key="viewport")
    st.markdown('<div class="viewer-caption"><span>DRAG TO ORBIT · SCROLL TO ZOOM · SHIFT + DRAG TO PAN</span><span>PERSPECTIVE</span></div>', unsafe_allow_html=True)
    dims = " × ".join(f"{v:g}" for v in mesh.extents)
    st.markdown(f'<div class="part-name">{TITLES[spec.shape_type]}</div><div class="part-detail">{html.escape(st.session_state.source)}</div><div class="stats"><div class="stat"><div class="stat-label">Outside dimensions</div><div class="stat-value">{dims} <small>mm</small></div></div><div class="stat"><div class="stat-label">Solid volume</div><div class="stat-value">{mesh.volume/1000:,.2f} <small>cm³</small></div></div><div class="stat"><div class="stat-label">Mesh integrity</div><div class="stat-value">Watertight <small>verified</small></div></div></div>', unsafe_allow_html=True)
    st.download_button("Download STL  ↓", data=stl, file_name=f"bolicad_{spec.shape_type}.stl", mime="model/stl", type="primary", width="stretch")
    st.caption("Export matches this preview. STL coordinates are millimetres; select mm when importing into a slicer.")
    with st.expander("Design decisions & specification"):
        st.markdown("**Assumptions and defaults**")
        if spec.assumptions:
            for assumption in spec.assumptions:
                st.write("• " + assumption)
        else:
            st.caption("All dimensions were explicitly supplied.")
        if spec.missing_parameters:
            st.caption("Defaulted parameters: " + ", ".join(spec.missing_parameters))
        if spec.hole_layout == "auto" and spec.holes:
            st.caption("Hole locations: " + ("evenly spaced vertically on the upright." if spec.shape_type == "bracket" else "four corner holes, or evenly spaced along the length for other counts."))
        st.json(spec.model_dump(), expanded=False)
        st.download_button("Download specification JSON", spec.model_dump_json(indent=2), "bolicad_spec.json", "application/json")
    st.caption("Three precise shape families. Geometry checks establish a closed solid, not structural strength or manufacturing tolerances.")

st.markdown('<div class="foot"><span>BoliCAD — From voice to 3D.</span><span>LANGUAGE BY SARVAM AI · GEOMETRY BY MANIFOLD</span></div>', unsafe_allow_html=True)
with st.expander("About this workspace & privacy"):
    st.caption("Commands and recordings are sent to Sarvam AI only when you use AI generation or transcription. Audio is kept in this browser session and is not written to disk by the app. Parametric geometry and STL export run on the server without AI. Missing dimensions use the defaults shown in the specification. This MVP supports brackets, plates, and open-top boxes only.")
