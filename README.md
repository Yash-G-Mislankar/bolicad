# BoliCAD — From voice to 3D

A multilingual Streamlit CAD workspace using real Sarvam AI APIs. Supports exactly
three editable parametric solids: L-shaped brackets, rectangular mounting plates,
and open-top boxes. Geometry uses Trimesh and Manifold3D; Plotly displays the same
triangles exported to STL. All dimensions are millimetres.

Source: [Yash-G-Mislankar/bolicad](https://github.com/Yash-G-Mislankar/bolicad).

Public app: [BoliCAD](https://bolicad-vzp2laiy7adimfjkudkme5.streamlit.app/).

[Open the prefilled Streamlit deployment form](https://share.streamlit.io/deploy?repository=Yash-G-Mislankar%2Fbolicad&branch=main&mainModule=app.py).

## Run

Requires Python 3.11 or newer (tested with Python 3.13).

```sh
cd bolicad                    # omit if this folder is your repository root
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Set `SARVAM_API_KEY` in the environment, `.streamlit/secrets.toml`, or a local
`.env` file. Templates contain empty values only. In this original multi-project
workspace, the parent `.env` is also supported. Keys are never sent to the browser.
Without a key, the parameter editor, 3D preview, and STL downloads still work.

## Use

1. Choose a language and record a command under 29 seconds, or type a description.
2. Review the transcription, then select **Generate Model**.
3. Inspect/orbit the solid; change dimensions and press **Update geometry**.
4. After generation, follow-up commands automatically use **Refine** context.
   For example: “Make it 120 mm tall; keep everything else the same.” Select
   **Create**, or an example prompt, to start a new design.
5. Download the STL or the JSON specification. STL has no embedded unit metadata;
   choose **mm** when importing into a slicer or another CAD tool.

The three example buttons populate the prompt; they do not fake an AI result.
The first displayed bracket is explicitly labelled **Starter design**.

## Dimensions and holes

- Bracket: height, width, depth, thickness, hole count and default hole diameter.
- Plate: length, width, thickness, hole count and default hole diameter.
- Box: outside length, width, height, and wall/bottom thickness; top is open.
- Automatic bracket holes are evenly spaced on the upright. Four plate holes
  use corner placement; other counts run along the length.
- Enable custom holes to edit their face, X/Y location and individual diameter.
  Custom diameters override the default diameter. The table row count must match
  the hole-count parameter. Upright Y means vertical height; base Y means depth.
- Dimensions are limited to 0.5–1000 mm; holes to 0–12. Holes require 0.5 mm edge
  and inter-hole clearance. These are geometric constraints, not strength ratings.
- Missing values use explicitly displayed defaults. Invalid/contradictory values
  produce clarification errors and retain the previous valid model.

## Deploy on Streamlit Community Cloud

Publish **the contents of this `bolicad` folder as the repository root**. The
existing BillSaathi application in the parent folder is a separate project.

1. The source is already pushed to **`Yash-G-Mislankar/bolicad`**, branch **`main`**.
2. At [Streamlit Community Cloud](https://share.streamlit.io), choose **Create app**
   and select that repository, branch `main`, main file **`app.py`**.
3. In **Advanced settings**, select **Python 3.13**. Add a root-level secret:

   ```toml
   SARVAM_API_KEY = "your actual key, entered only in Cloud secrets"
   ```

4. Deploy, set app visibility to public, and test the generated HTTPS URL.

No extra OS packages, database, Node server, or native CAD installation are needed.
The public app is deployed. Configure `SARVAM_API_KEY` in Cloud secrets to enable
voice and AI generation; geometry editing and STL export also work without a key.

[Official deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
and [Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Architecture and privacy

`audio → Saaras v4 → Sarvam-105B JSON → Pydantic → Manifold booleans → Plotly/STL`

`ai_service.py` handles official SDK calls, bounded requests and safe error messages.
`cad_schema.py` validates shape-specific dimensions and hole locations.
`geometry.py` has predefined constructors only; AI-generated code is never executed.
`viewer.py` renders the export mesh. `app.py` manages the UI and session state.

Audio is held in the active Streamlit session and never saved by the app. Commands
and recordings are sent to Sarvam when AI generation/transcription is requested.
Sarvam's own processing and retention policies apply. Pure geometry results are
cached in server memory for up to one hour. No cross-user AI response cache is used.
Microphone capture requires browser permission and HTTPS (or localhost).

## Verification

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
python tests/live_smoke.py    # opt-in: real API requests and credits
```

Verified locally on 1 November 2026:

| Check | Result |
|---|---|
| Offline schema, geometry, STL and UI state tests | 16 pass |
| GitHub Actions on Linux/Python 3.13, dependency installation and all 16 tests | Pass |
| English bracket, plate and box via real Sarvam-105B | Pass |
| Follow-up height edit preserves other parameters | Pass |
| Impossible box walls rejected using real API | Pass |
| Real Bulbul Marathi fixture → Saaras v4 → CAD | Pass |
| Browser microphone capture → real Saaras → CAD, prerecorded Marathi fixture | Pass |
| Browser dimension editing, invalid edit rollback, STL download | Pass |
| Browser real text generation, contextual edit, orbit/reset | Pass |
| 390 px and 320 px layout, no horizontal overflow | Pass |
| Public Cloud load, parameter editing, invalid edit rollback and STL export | Pass |
| Public Cloud 390 px and 320 px layouts, no horizontal overflow | Pass |
| Public Cloud English generation and contextual height edit with configured secrets | Pass |
| Public Cloud microphone → Saaras v4 → CAD using prerecorded Marathi fixture | Pass |

Synthetic speech is explicitly a test fixture, not a recording of a human user.
The exported STL is reloaded and checked for watertightness, positive volume,
single-body connectivity, and agreement with preview bounds before download.
Optional spoken responses are not implemented. A human user's physical microphone
and permission prompts still need a manual check on their own device.

Official API references:
[chat JSON output](https://docs.sarvam.ai/api/token-factory/chat-completions),
[Saaras REST transcription](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api).
