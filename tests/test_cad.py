import io
import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import trimesh
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_service import ServiceError, understand, transcribe, normalize_explicit_units
from cad_schema import ShapeSpec, default_spec
from geometry import build_mesh, export_stl, connected_bodies


class GeometryTests(unittest.TestCase):
    def test_all_families_export_closed_single_solid(self):
        for shape in ("bracket", "plate", "box"):
            with self.subTest(shape=shape):
                mesh = build_mesh(default_spec(shape))
                exported = trimesh.load(io.BytesIO(export_stl(mesh)), file_type="stl")
                self.assertTrue(exported.is_volume)
                self.assertTrue(exported.is_watertight)
                self.assertEqual(connected_bodies(exported), 1)
                np.testing.assert_allclose(exported.extents, mesh.extents, rtol=1e-6)
                self.assertAlmostEqual(exported.volume, mesh.volume, delta=.01)

    def test_box_has_open_cavity_and_solid_floor(self):
        mesh = build_mesh(default_spec("box"))
        expected = 100*70*50 - 94*64*47
        self.assertAlmostEqual(mesh.volume, expected, places=3)
        self.assertEqual(mesh.euler_number, 2)

    def test_bracket_holes_are_real_and_through_upright(self):
        mesh = build_mesh(default_spec("bracket"))
        bore = 96 / 2 * (2.5**2) * math.sin(2*math.pi/96) * 4
        expected = 50*40*4 + 50*4*80 - 50*4*4 - 2*bore
        self.assertAlmostEqual(mesh.volume, expected, delta=.02)
        self.assertEqual(mesh.euler_number, -2)

    def test_plate_four_bores_remove_expected_volume(self):
        mesh = build_mesh(default_spec("plate"))
        expected = 100*60*4 - 4*(96/2*2.5**2*math.sin(2*math.pi/96))*4
        self.assertAlmostEqual(mesh.volume, expected, delta=.02)
        self.assertEqual(mesh.euler_number, -6)

    def test_parameter_edits_change_mesh_and_preserve_other_dimensions(self):
        spec = default_spec()
        data = spec.model_dump()
        data["dimensions"]["height"] = 120
        edited = ShapeSpec.model_validate(data)
        mesh = build_mesh(edited)
        np.testing.assert_allclose(mesh.extents, [50, 40, 120])
        self.assertGreater(mesh.volume, build_mesh(spec).volume)
        self.assertEqual(edited.holes[0].y, 4 + 116/3)

    def test_no_holes(self):
        spec = ShapeSpec(shape_type="bracket", dimensions={"hole_count":0})
        mesh = build_mesh(spec)
        self.assertEqual(len(spec.holes), 0)
        self.assertEqual(mesh.euler_number, 2)

    def test_custom_base_holes(self):
        spec = ShapeSpec(shape_type="bracket", dimensions={"hole_count":1}, hole_layout="custom",
                         holes=[dict(face="base",x=25,y=22,diameter=6)])
        mesh = build_mesh(spec)
        self.assertTrue(mesh.is_volume)
        self.assertEqual(mesh.euler_number, 0)

    def test_invalid_dimensions(self):
        cases = [
            dict(shape_type="bracket",dimensions={"height":-1}),
            dict(shape_type="bracket",dimensions={"thickness":50}),
            dict(shape_type="box",dimensions={"wall_thickness":40}),
            dict(shape_type="box",dimensions={"height":3,"wall_thickness":3}),
            dict(shape_type="plate",dimensions={"length":float("nan")}),
            dict(shape_type="plate",dimensions={"width":float("inf")}),
            dict(shape_type="plate",dimensions={"hole_count":2.4}),
            dict(shape_type="plate",dimensions={"hole_count":13}),
            dict(shape_type="plate",dimensions={"hole_diameter":90}),
            dict(shape_type="bracket",dimensions={"height":15,"hole_count":8}),
            dict(shape_type="plate",dimensions={"radius":5}),
            dict(shape_type="plate",dimensions={},units="cm"),
            dict(shape_type="sphere",dimensions={}),
            dict(shape_type="box",dimensions={},invalid_parameters=["Which height: 20 or 30 mm?"]),
        ]
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                ShapeSpec.model_validate(data)

    def test_custom_holes_reject_edge_overlap_and_count_mismatch(self):
        holes = [
            [dict(x=1,y=20,diameter=5)],
            [dict(x=20,y=20,diameter=5),dict(x=21,y=20,diameter=5)],
            [dict(x=20,y=20,diameter=5,face="upright")],
        ]
        for h in holes:
            with self.subTest(holes=h), self.assertRaises(ValidationError):
                ShapeSpec(shape_type="plate", dimensions={"hole_count":len(h)}, hole_layout="custom", holes=h)
        with self.assertRaises(ValidationError):
            ShapeSpec(shape_type="plate", dimensions={"hole_count":2}, hole_layout="custom", holes=[])

    def test_defaults_are_explicit_and_schema_forbids_code(self):
        spec = default_spec("box")
        self.assertEqual(len(spec.assumptions), 4)
        with self.assertRaises(ValidationError):
            ShapeSpec(shape_type="box", dimensions={}, code="print('unsafe')")


class APITests(unittest.TestCase):
    def client_with_response(self, payload):
        client = Mock()
        client.chat.completions.return_value = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content=payload))])
        return client

    def test_edit_sends_validated_current_state_to_real_sdk_shape(self):
        spec = default_spec()
        client = self.client_with_response(spec.model_dump_json())
        understand(client, "Make the bracket taller", spec)
        args = client.chat.completions.call_args.kwargs
        self.assertEqual(args["model"], "sarvam-105b")
        self.assertEqual(args["response_format"]["type"], "json_schema")
        self.assertTrue(args["response_format"]["json_schema"]["strict"])
        self.assertIn('"height": 80.0', args["messages"][-1]["content"])

    def test_untrusted_response_must_validate(self):
        for payload in ['{"shape_type":"sphere","dimensions":{}}', 'print(1)', '{}']:
            with self.subTest(payload=payload), self.assertRaises(ServiceError):
                understand(self.client_with_response(payload), "create something")

    def test_audio_validation_prevents_api_call(self):
        client = Mock()
        with self.assertRaises(ServiceError):
            transcribe(client, b"not audio", "mr-IN")
        client.speech_to_text.transcribe.assert_not_called()

    def test_metadata_type_error_retries_original_command_without_changing_dimensions(self):
        valid = default_spec("plate").model_dump()
        valid["dimensions"].update(length=400,width=300,thickness=30,hole_count=0)
        invalid = dict(valid, assumptions=[{"thickness": "height mapped to thickness"}])
        client = self.client_with_response(json.dumps(valid))
        good = client.chat.completions.return_value
        bad = SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop",message=SimpleNamespace(content=json.dumps(invalid)))])
        client.chat.completions.side_effect = [bad, good]
        spec = understand(client, "Actually a block 30 cm wide, 40 cm long, 3 cm high")
        self.assertEqual(spec.dimensions["thickness"], 30)
        self.assertEqual(spec.dimensions["hole_count"], 0)
        self.assertEqual(client.chat.completions.call_count, 2)

    def test_persistent_metadata_error_does_not_blame_user_dimensions(self):
        data = default_spec().model_dump()
        data["missing_parameters"] = [{"height": None}]
        client = self.client_with_response(json.dumps(data))
        with self.assertRaisesRegex(ServiceError, "could not return a valid design specification"):
            understand(client, "Make a bracket")
        self.assertEqual(client.chat.completions.call_count, 2)

    def test_impossible_dimensions_do_not_trigger_silent_ai_repair(self):
        data = default_spec("box").model_dump()
        data["dimensions"]["wall_thickness"] = 100
        client = self.client_with_response(json.dumps(data))
        with self.assertRaisesRegex(ServiceError, "Wall thickness"):
            understand(client, "Make the wall 100 mm thick")
        client.chat.completions.assert_called_once()

    def test_explicit_unit_conversion_is_deterministic_before_inference(self):
        self.assertEqual(normalize_explicit_units("30 सेंटीमीटर विड्थ 40 cm length 3 सेंटीमीटर हाइट"),
                         "300 mm विड्थ 400 mm length 30 mm हाइट")
        self.assertEqual(normalize_explicit_units("३ सेंटीमीटर, -2 cm, 1.5 inches"),
                         "30 mm, -20 mm, 38.10 mm")
        self.assertEqual(normalize_explicit_units("5 mm holes, two holes, model3cm"),
                         "5 mm holes, two holes, model3cm")


if __name__ == "__main__":
    unittest.main()
