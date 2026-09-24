"""Execute com Python 3.12 x64 e dependências de requirements.txt instaladas."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
from PySide6.QtWidgets import QApplication
from PIL import Image
from desktop import app_icon

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--work-dir", type=Path, default=root / "build")
args = parser.parse_args()
build = args.work_dir.resolve()
build.mkdir(parents=True, exist_ok=True)
app = QApplication([])
png = build / "icon.png"
ico = build / "icon.ico"
app_icon().pixmap(128, 128).save(str(png))
with Image.open(png) as image:
    image.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)])
# Não incorporar DLLs de outros programas presentes no PATH da máquina de build.
environment = os.environ.copy()
windows = Path(environment.get("SystemRoot", r"C:\Windows"))
environment["PATH"] = os.pathsep.join([str(Path(sys.executable).parent),
                                      str(windows / "System32"), str(windows)])
subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
    "--onefile", "--windowed", "--name", "DownloadStudio", "--icon", str(ico),
    "--distpath", str(root.parent), "--workpath", str(build / "pyinstaller"),
    "--specpath", str(build), "--exclude-module", "tkinter",
    "--exclude-module", "customtkinter", "--exclude-module", "pystray",
    str(root / "launcher.py")], check=True, env=environment)
