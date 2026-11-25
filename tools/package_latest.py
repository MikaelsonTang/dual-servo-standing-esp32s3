"""Build the two current, board-specific workshop downloads."""
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OMIT = {'__pycache__', 'recordings', '.venv', '.pytest_cache'}


def files(base, singles, directories):
    selected = [base / name for name in singles]
    for name in directories:
        selected.extend(path for path in (base / name).rglob('*') if path.is_file())
    for path in sorted(set(selected)):
        if not path.is_file():
            raise FileNotFoundError(path)
        if any(part in OMIT for part in path.relative_to(base).parts) or path.suffix in {'.pyc', '.pyo'}:
            continue
        yield path


def build(base, destination, prefix, singles, directories):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files(base, singles, directories):
            archive.write(path, (Path(prefix) / path.relative_to(base)).as_posix())
    with ZipFile(destination) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f'Corrupt archive entry: {bad}')
        names = archive.namelist()
        if not names or any('v20' in name.lower() or 'v24' in name.lower() or 'v25' in name.lower() for name in names):
            raise ValueError('Outdated version found in release package')
    digest = sha256(destination.read_bytes()).hexdigest()
    print(f'{destination.relative_to(ROOT)}  {len(names)} files  SHA256 {digest}')
    return digest


def main():
    build(ROOT, ROOT / 'downloads/HD1910_S3_V21.zip', 'HD1910_S3_V21',
          ['00_setup.cmd', '01_flash.cmd', '02_open_demo.cmd', '03_read_joint_zero.cmd',
           'README.md', 'THIRD_PARTY_NOTICES.md', 'requirements-workshop.txt',
           'tools/flash_v21.py', 'tools/read_joint_zero.py'],
          ['desktop', 'docs', 'firmware/v21/policy_shadow', 'firmware/prebuilt/v21', 'mechanical/stl'])
    c3 = ROOT / 'esp32c3'
    digest = build(c3, c3 / 'downloads/HD1910_C3_V26.zip', 'HD1910_C3_V26',
                   ['00_setup.cmd', '01_flash.cmd', '02_open_demo.cmd', '03_read_joint_zero.cmd',
                    'README.md', 'THIRD_PARTY_NOTICES.md', 'requirements.txt', 'flash_c3.py',
                    'manifest.json', 'runtime_identity.json'],
                   ['desktop', 'docs', 'firmware/policy_shadow', 'mechanical/stl',
                    'release', 'tests', 'tools', 'validation'])
    (c3 / 'downloads/SHA256SUMS.txt').write_text(f'{digest}  HD1910_C3_V26.zip\n', encoding='ascii')


if __name__ == '__main__':
    main()
