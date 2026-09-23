"""Build a Windows x64 standalone GUI; assets and verified engines are required."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import PyInstaller.__main__

BASE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distpath', type=Path, default=BASE / 'dist')
    parser.add_argument('--workpath', type=Path, default=BASE / 'build')
    args = parser.parse_args()
    # Do not collect unrelated DLLs (e.g. Poppler's incompatible icuuc.dll) from PATH.
    os.environ["PATH"] = os.pathsep.join([
        str(Path(sys.executable).parent),
        str(Path(os.environ["SystemRoot"]) / "System32"),
        os.environ["SystemRoot"],
    ])
    for name in ("cloudflared", "frpc"):
        binary = BASE / "bundled_engines" / f"{name}-amd64.exe"
        info = json.loads(binary.with_suffix(".json").read_text(encoding="utf-8"))
        if hashlib.sha256(binary.read_bytes()).hexdigest() != info["sha256"]:
            raise ValueError(f"Invalid engine checksum: {name}")
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--windowed", "--noupx",
        "--name", "ElysiaTunnel", "--icon", str(BASE / "assets" / "app.ico"),
        "--distpath", str(args.distpath), "--workpath", str(args.workpath),
        "--specpath", str(args.workpath),
        "--additional-hooks-dir", str(BASE / 'packaging' / 'hooks'),
        "--add-data", f"{BASE / 'qml'};qml",
        "--add-data", f"{BASE / 'assets'};assets",
        "--add-data", f"{BASE / 'bundled_engines'};bundled_engines",
        "--add-data", f"{BASE / 'third_party_licenses'};third_party_licenses",
        "--exclude-module", "tkinter",
        str(BASE / "tunnel_gui.pyw"),
    ])


if __name__ == "__main__":
    main()
