"""UI state regressions; offline and no Sarvam credits required."""
import sys
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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


if __name__ == "__main__":
    unittest.main()
