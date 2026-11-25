"""Verify that the published downloads contain one current board build each."""
import hashlib
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class ReleasePackageTests(unittest.TestCase):
    def test_s3_package(self):
        with ZipFile(ROOT / 'downloads/HD1910_S3_V21.zip') as archive:
            prefix = 'HD1910_S3_V21/'
            ui = archive.read(prefix + 'desktop/event_app.py').decode('utf-8')
            data = archive.read(prefix + 'desktop/data.py').decode('utf-8')
            self.assertIn('ESP32-S3 · V21', ui)
            self.assertIn('保存当前直立关节零位', ui)
            self.assertIn("FW = 'HD1910_RECOVERY_V21'", data)
            manifest = json.loads(archive.read(prefix + 'firmware/prebuilt/v21/manifest.json'))
            for name, digest in manifest['files'].items():
                image = archive.read(prefix + 'firmware/prebuilt/v21/' + name)
                self.assertEqual(hashlib.sha256(image).hexdigest(), digest)
            self.assertFalse(any(old in name.lower() for name in archive.namelist()
                                 for old in ('v20', 'v24', 'v25')))

    def test_c3_package(self):
        with ZipFile(ROOT / 'esp32c3/downloads/HD1910_C3_V26.zip') as archive:
            prefix = 'HD1910_C3_V26/'
            ui = archive.read(prefix + 'desktop/event_app.py').decode('utf-8')
            data = archive.read(prefix + 'desktop/data.py').decode('utf-8')
            self.assertIn('C3 完整测试 · V26', ui)
            self.assertIn('保存当前直立关节零位', ui)
            self.assertIn("FW = 'HD1910_C3_TEST_V26'", data)
            manifest = json.loads(archive.read(prefix + 'manifest.json'))
            for name, digest in manifest['flash_files'].items():
                image = archive.read(prefix + 'release/' + name)
                self.assertEqual(hashlib.sha256(image).hexdigest(), digest)
            self.assertFalse(any(old in name.lower() for name in archive.namelist()
                                 for old in ('v20', 'v24', 'v25')))


if __name__ == '__main__':
    unittest.main()
