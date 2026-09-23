"""Check the standalone bundle without running a tunnel or accessing an account."""
import argparse
import hashlib
import json
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader


def verify(executable):
    executable = Path(executable)
    root = Path(__file__).resolve().parents[1]
    archive = CArchiveReader(str(executable))
    names = {name.replace('\\', '/'): name for name in archive.toc}
    for folder in ('qml', 'assets', 'third_party_licenses'):
        for source in (root / folder).rglob('*'):
            if source.is_file():
                name = source.relative_to(root).as_posix()
                assert archive.extract(names[name]) == source.read_bytes(), name
    for engine in ('cloudflared', 'frpc'):
        stem = f'bundled_engines/{engine}-amd64'
        manifest = json.loads(archive.extract(names[stem + '.json']))
        digest = hashlib.sha256(archive.extract(names[stem + '.exe'])).hexdigest()
        assert digest == manifest['sha256'], engine
    for suffix in ('opengl32sw.dll', 'qwindows.dll', 'Qt6Widgets.dll',
                   'QtQuick/Effects/qmldir', 'QtQuick/Controls/Material/qmldir',
                   'QtQuick/Controls/Basic/qmldir'):
        assert any(name.endswith(suffix) for name in names), suffix
    assert not any('WebEngine' in name for name in names)
    assert not any(name.lower().endswith('/icuuc.dll') or name.lower() == 'icuuc.dll' for name in names)
    sha = hashlib.sha256(executable.read_bytes()).hexdigest()
    executable.with_suffix('.exe.sha256').write_text(f'{sha}  {executable.name}\n', encoding='utf-8')
    print(f'PASS bundle contents and engine checksums: {executable.stat().st_size / 2**20:.2f} MiB')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    verify(parser.parse_args().executable)
