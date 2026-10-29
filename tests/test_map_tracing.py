import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from mhfz_builder.map_browser import TRACING, native_atlases, render_overview, traced_overviews


class MapTracingTests(unittest.TestCase):
    def test_imported_user_review_preserves_camp_and_corrects_cloud_fortress(self):
        forest = next(r for r in TRACING["bindings"]["2"] if r["native_index"] == 1)
        self.assertEqual(forest["display_crop"], [0, 0, 256, 240])
        self.assertEqual(forest["visual_review"], "correct")
        self.assertNotEqual(forest["review_state"], "user_confirmed", "No exact map-ID checkbox was selected")
        self.assertEqual(TRACING["bindings"]["91"][0]["native_index"], 52)
        self.assertEqual(TRACING["atlas_labels"]["51"]["names"], ["Great Island"])
        self.assertIn("Short Tower", TRACING["atlas_labels"]["15"]["names"][0])

    def test_unsure_pending_and_non_map_decisions_are_not_promoted(self):
        unsure = next(r for r in TRACING["bindings"]["8"] if r["native_index"] == 9)
        self.assertEqual(unsure["visual_review"], "unsure")
        self.assertNotIn("display_crop", unsure)
        self.assertEqual(TRACING["atlas_labels"]["39"]["review_state"], "not_a_map")
        self.assertFalse(any(r["native_index"] == 39 for records in TRACING["bindings"].values() for r in records))
        pending = next(r for r in TRACING["bindings"]["49"] if r["native_index"] == 32)
        self.assertNotEqual(pending.get("visual_review"), "correct")

    def test_historical_mislabels_are_corrected_without_rewriting_sources(self):
        expected = {"43": "Tidal Island", "44": "Flower Field", "49": "White Lake Day", "50": "White Lake Night"}
        for key, label in expected.items():
            self.assertIn(label, " ".join(TRACING["atlas_labels"][key]["names"]))
            self.assertIn("correction", TRACING["atlas_labels"][key])
        self.assertEqual(TRACING["bindings"]["62"][0]["review_state"], "user_confirmed")
        self.assertNotEqual(TRACING["bindings"]["15"][0]["review_state"], "user_confirmed")

    def test_display_crop_hides_footer_without_modifying_original_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "native.png"; original = b"original source payload"; path.write_bytes(original)
            record = {"path": path, "label": "World's End", "status": "user confirmed", "width": 256, "height": 256, "display_crop": [0, 0, 256, 232]}
            html = render_overview(record, "World's End")
            self.assertIn("aspect-ratio:256/232", html)
            self.assertIn("overflow:hidden", html)
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                render_overview(dict(record, display_crop=[0, 0, 256, 300]), "Invalid")

    def test_tracing_requires_exact_native_revision_and_preserves_old_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); png = root / "000.png"; png.write_bytes(b"fixture")
            sha = hashlib.sha256(png.read_bytes()).hexdigest()
            index = root / "index.json"; source = [{"file": png.name, "sha256": sha, "index": 0, "width": 256, "height": 256, "visualLabel": "Historical label"}]
            index.write_text(json.dumps(source))
            trace = {"atlas_labels": {"0": {"sha256": sha, "names": ["Corrected label"], "review_state": "variant_pending"}},
                     "bindings": {"1": [{"native_index": 0, "sha256": sha, "label": "Candidate", "review_state": "variant_pending", "notes": "Review needed", "evidence": []}]}}
            config = {"native_map_index": str(index)}
            with patch("mhfz_builder.map_browser.TRACING", trace):
                atlas = native_atlases(config)[0]
                self.assertEqual(atlas["historical_label"], "Historical label")
                self.assertEqual(atlas["label"], "Corrected label")
                self.assertIn("1", traced_overviews(config))
                trace["bindings"]["1"][0]["sha256"] = "0" * 64
                self.assertNotIn("1", traced_overviews(config))
            self.assertEqual(json.loads(index.read_text()), source)
