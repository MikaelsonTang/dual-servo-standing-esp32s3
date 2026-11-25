import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flash_v21', ROOT / 'tools' / 'flash_v21.py')
flash = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flash)


class V21PackageTests(unittest.TestCase):
    def test_hashes_offsets_and_chip(self):
        manifest = flash.checked_images()
        args = flash.command('COM99', manifest)
        self.assertEqual(manifest['startup_tolerance_counts'], 48)
        self.assertIsNone(manifest['recovery_total_deadline'])
        self.assertEqual(manifest['flash_offsets'], {
            'policy_shadow.ino.bootloader.bin': '0x0',
            'policy_shadow.ino.partitions.bin': '0x8000',
            'boot_app0.bin': '0xe000',
            'policy_shadow.ino.bin': '0x10000',
        })
        self.assertEqual(args[args.index('--chip') + 1], 'esp32s3')
        self.assertNotIn('erase_flash', args)


if __name__ == '__main__':
    unittest.main()
