"""UI state regressions; offline and no Sarvam credits required."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_service import ServiceError


class WorkspaceTests(unittest.TestCase):
    def app(self):
        app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=20)
        self.assertFalse(app.exception)
        return app

    def button(self, app, label):
        return next(x for x in app.button if x.label == label)

    def test_valid_edit_updates_current_and_refinement_context(self):
        app = self.app()
        next(x for x in app.number_input if x.label == "Height (mm)").set_value(120)
        self.button(app, "Update geometry").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.spec.dimensions["height"], 120)
        self.assertEqual(app.session_state.intent, "Refine")

    def test_invalid_edit_preserves_previous_valid_solid(self):
        app = self.app()
        next(x for x in app.number_input if x.label == "Thickness (mm)").set_value(80)
        self.button(app, "Update geometry").click().run()
        self.assertTrue(app.error)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.spec.dimensions["thickness"], 4)

    def test_family_switch_and_examples(self):
        app = self.app()
        next(x for x in app.selectbox if x.label == "Geometry family").set_value("box").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.spec.shape_type, "box")
        self.button(app, "L-bracket · 80 × 50 × 40 mm").click().run()
        self.assertIn("L-shaped bracket", app.session_state.prompt)
        self.assertEqual(app.session_state.intent, "Create")

    def test_ai_failure_finishes_status_and_preserves_current_model(self):
        app = self.app()
        app.text_area[0].set_value("Make a block").run()
        with patch("ai_service.understand", side_effect=ServiceError("Please clarify the height.")):
            self.button(app, "Generate Model  →").click().run()
        self.assertFalse(app.exception)
        self.assertIn("Please clarify the height", app.error[0].value)
        self.assertEqual(app.status[0].state, "error")
        self.assertIn("Model not changed", app.status[0].label)
        self.assertEqual(app.session_state.spec.shape_type, "bracket")


if __name__ == "__main__":
    unittest.main()
