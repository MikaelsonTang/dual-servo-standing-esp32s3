"""Portable package checks; no serial or motor activity."""
import hashlib,importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flash_c3',ROOT/'flash_c3.py')
flash=importlib.util.module_from_spec(spec);spec.loader.exec_module(flash)

class PublicationChecks(unittest.TestCase):
    def test_published_files_match_manifest(self):
        self.assertEqual(flash.checked_images(),ROOT/'release')
    def test_custom_zero_or_modified_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name in ('firmware','desktop','release'):shutil.copytree(ROOT/name,p/name)
            shutil.copy2(ROOT/'manifest.json',p/'manifest.json')
            zero=p/'firmware/policy_shadow/joint_limits.h'
            original=zero.read_bytes();zero.write_text(zero.read_text(encoding='utf-8').replace('337','350'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Custom source'):flash.checked_images(p)
            zero.write_bytes(original)
            image=p/'release/application.bin';image.write_bytes(b'broken')
            with self.assertRaisesRegex(ValueError,'checksum'):flash.checked_images(p)
    def test_c3_chip_and_offsets(self):
        args=flash.command('COM123',ROOT/'release')
        self.assertEqual(args[args.index('--chip')+1],'esp32c3')
        for offset in ('0x0','0x8000','0xe000','0x10000'):self.assertIn(offset,args)
        self.assertNotIn('esp32s3',args)
    def test_runtime_sources_unchanged_from_validated_revision(self):
        source=ROOT.parents[1]/'c3_recovery'
        if not source.exists():self.skipTest('Author workspace comparison only')
        for directory in ('firmware','desktop'):
            for p in (ROOT/directory).rglob('*'):
                if p.suffix in ('.ino','.h','.c','.py'):
                    self.assertEqual(p.read_text(encoding='utf-8'),(source/p.relative_to(ROOT)).read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
