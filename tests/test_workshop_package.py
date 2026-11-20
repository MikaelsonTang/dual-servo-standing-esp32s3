import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('flash_workshop',ROOT/'tools/flash_workshop.py')
flash=importlib.util.module_from_spec(spec);spec.loader.exec_module(flash)

class PackageTests(unittest.TestCase):
    def test_hashes_and_exact_offsets(self):
        directory,m=flash.checked_images()
        args=flash.command('COM99',directory,m)
        self.assertEqual(m['flash_offsets'],{'policy_shadow.ino.bootloader.bin':'0x0','policy_shadow.ino.partitions.bin':'0x8000','boot_app0.bin':'0xe000','policy_shadow.ino.bin':'0x10000'})
        self.assertIn('write_flash',args);self.assertNotIn('erase_flash',args)
        self.assertEqual(args[args.index('--chip')+1],'esp32s3')
    def test_modified_binaries_and_custom_calibration_are_refused(self):
        for change in ['binary','zero','mount']:
            with tempfile.TemporaryDirectory() as temp:
                dest=Path(temp)
                for name in ['firmware/prebuilt/v20','firmware/policy_shadow','desktop']:
                    shutil.copytree(ROOT/name,dest/name)
                if change=='binary':
                    f=dest/'firmware/prebuilt/v20/policy_shadow.ino.bin';f.write_bytes(f.read_bytes()+b'changed')
                elif change=='zero':
                    f=dest/'desktop/data.py';f.write_text(f.read_text(encoding='utf-8').replace('{1:337,2:2872}','{1:350,2:2850}'),encoding='utf-8')
                else:
                    f=dest/'firmware/policy_shadow/calibration_generated.h';f.write_text(f.read_text(encoding='utf-8')+'\n// custom mount\n',encoding='utf-8')
                with patch.object(flash,'ROOT',dest):
                    with self.assertRaises(ValueError):flash.checked_images()

if __name__=='__main__':unittest.main()
