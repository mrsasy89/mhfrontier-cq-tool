import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from scripts.check_cq_parity import check


class CQParityTests(unittest.TestCase):
    def test_pinned_inherited_source_and_reviewed_exceptions_match(self):
        self.assertEqual(check(Path(__file__).resolve().parents[1])['problems'], [])

    def test_unreviewed_source_change_is_detected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'docs').mkdir(); (root/'src').mkdir()
            source=root/'src/editor.ts'; source.write_bytes(b'const value = 1;\r\n')
            row={'path':'src/editor.ts','baseline_sha256':hashlib.sha256(b'const value = 1;\n').hexdigest()}
            (root/'docs/cq-baseline.json').write_text(json.dumps({'revision':'pinned','files':[row]}),encoding='utf-8')
            self.assertEqual(check(root)['problems'], [])
            source.write_bytes(b'const value = 2;\n')
            self.assertTrue(check(root)['problems'])
