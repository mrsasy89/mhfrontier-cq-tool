from pathlib import Path
import tempfile
import json
import hashlib
import unittest
from unittest.mock import patch
from test_core import fixture
from mhfz_builder.binary import CATALOG
from mhfz_builder.config import initialize
from mhfz_builder.corpus import scan
from mhfz_builder.map_browser import rows, legend, gallery
from mhfz_builder.wizard import Console, choose_map


class MapBrowserTests(unittest.TestCase):
    def project(self, root):
        source = root / "corpus"; source.mkdir()
        (source / "65026d0.bin").write_bytes(fixture())
        config = initialize(root / "config.local.json", source, None)
        images = root / "images"; (images / "Tower 03").mkdir(parents=True)
        (images / "Tower 03/5.png").write_bytes(b"image fixture; not executed")
        return dict(config, map_images_directory=str(images))

    def test_legend_has_exact_catalog_names_and_all_pages_wrap(self):
        items = rows()
        self.assertEqual({r["id"] for r in items}, set(CATALOG["maps"]))
        self.assertIn("MAP LEGEND", legend(items))
        self.assertEqual(legend(items, 0), legend(items, (len(items) + 11) // 12))
        self.assertIn("N/P", legend(items))

    def test_counts_use_the_index_and_local_assets_without_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.project(Path(tmp)); scan(config)
            item = next(r for r in rows(config) if r["id"] == "15")
            self.assertEqual(item["references"], 1)
            self.assertEqual(item["asset_folder"], "Tower 03")
            self.assertEqual(item["images"][0].name, "5.png")

    def test_gallery_uses_file_urls_and_opens_only_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.project(Path(tmp))
            with patch("mhfz_builder.map_browser.webbrowser.open", return_value=True) as browser:
                result = gallery(config)
                browser.assert_not_called()
                output = Path(result["saved"]).read_text(encoding="utf-8")
                self.assertIn("file:///", output)
                self.assertIn("Tower%2003", output)
                self.assertIn("No local preview available", output)
                self.assertIn("do not certify", output)
                self.assertTrue(gallery(config, True, "15")["opened"])
                self.assertTrue(browser.call_args.args[0].endswith("#map-15"))

    def test_legend_navigation_and_map_selection_need_no_additional_answers(self):
        values = iter(["n", "p", "15"]); messages = []
        ui = Console(lambda _: next(values), messages.append)
        result = choose_map(ui)
        self.assertIn("Tower 3", result)
        self.assertIn("map ID 15", result)
        self.assertTrue(any("Page 2/" in m for m in messages))

    def test_preview_does_not_select_the_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.project(Path(tmp)); values = iter(["v 15", "15"])
            ui = Console(lambda _: next(values), lambda _: None)
            with patch("mhfz_builder.map_browser.webbrowser.open", return_value=True):
                result = choose_map(ui, config)
            self.assertIn("map ID 15", result)

    def test_unknown_map_and_unsafe_gallery_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.project(Path(tmp))
            with self.assertRaises(ValueError):
                gallery(config, map_id="99999")
            with self.assertRaises(ValueError):
                gallery(dict(config, workspace=config["source"]))

    def test_multiple_full_overviews_stay_separate_from_area_crops_and_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = self.project(root)
            records = []
            for n in (1, 2):
                path = root / f"tower-full-{n}.png"; path.write_bytes(bytes([n]))
                records.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "label": f"Overview {n}", "status": "user reference"})
            index = root / "bindings.local.json"; index.write_text(json.dumps({"15": records}))
            config["map_overview_index"] = str(index)
            items = {r["id"]: r for r in rows(config)}
            self.assertEqual(len(items["15"]["overviews"]), 2)
            self.assertEqual(items["14"]["overviews"], [])
            output = Path(gallery(config)["saved"]).read_text(encoding="utf-8")
            self.assertIn("tower-full-1.png", output)
            self.assertIn("tower-full-2.png", output)
            self.assertIn("Separate area crops", output)

    def test_full_overview_hash_mismatch_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = self.project(root)
            path = root / "full.png"; path.write_bytes(b"changed")
            index = root / "bindings.local.json"; index.write_text(json.dumps({"1": [{"path": str(path), "sha256": "0" * 64, "label": "Siege", "status": "user reference"}]}))
            with self.assertRaisesRegex(ValueError, "hash/type"):
                rows(dict(config, map_overview_index=str(index)))

    def test_unassigned_native_assets_are_preserved_but_not_dumped_in_app_gallery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); config = self.project(root)
            records = []
            for n in range(2):
                path = root / f"native-{n}.png"; path.write_bytes(bytes([n]))
                records.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "index": n, "width": 1024, "height": 256})
            index = root / "native-index.json"; index.write_text(json.dumps(records))
            result = gallery(dict(config, native_map_index=str(index)))
            self.assertEqual(result["native_atlases"], 2)
            output = Path(result["saved"]).read_text(encoding="utf-8")
            self.assertNotIn("native-0.png", output)
            self.assertNotIn("native-1.png", output)
            self.assertNotIn("review-filter", output)
            self.assertNotIn("data-review", output)
            self.assertTrue((root / "native-0.png").is_file())

    def test_L_shows_every_map_including_last_page_and_allows_immediate_selection(self):
        answers = iter(["n", "L", "97"]); messages = []
        ui = Console(lambda _: next(answers), messages.append)
        result = choose_map(ui)
        complete = next(m for m in messages if "MAP LEGEND" in m and "Historic Site" in m)
        for item in CATALOG["maps"].values():
            self.assertIn(item["name"], complete)
        self.assertIn("map ID 97", result)

    def test_retired_R_does_not_open_a_review_page(self):
        answers = iter(["R", "15"]); messages = []
        ui = Console(lambda _: next(answers), messages.append)
        with patch("mhfz_builder.map_browser.gallery") as browser:
            result = choose_map(ui)
        browser.assert_not_called()
        self.assertIn("map ID 15", result)
        self.assertTrue(any("handled in chat" in m for m in messages))
