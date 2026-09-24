"""Ponto de entrada com diagnóstico inclusive para falhas de importação."""
import ctypes
import os
from pathlib import Path
import sys
import traceback

if __name__ == "__main__":
    try:
        from desktop import main
        main()
    except Exception:
        detail = traceback.format_exc()
        if "--smoke-test" in sys.argv:
            report = Path(sys.argv[sys.argv.index("--smoke-test") + 1]).with_suffix(".error.log")
        else:
            report = Path(os.environ.get("LOCALAPPDATA", ".")) / "DownloadStudio" / "erro-inicializacao.log"
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(detail, encoding="utf-8")
        except OSError:
            pass
        if "--smoke-test" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, f"Não foi possível abrir Download Studio.\nDetalhes: {report}\n\n{detail[-1500:]}", "Download Studio", 16)
        raise SystemExit(1)
