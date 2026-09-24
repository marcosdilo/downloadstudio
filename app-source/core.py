"""Organizador de Downloads para Windows — Python 3.10 ou superior.

Instalação: py -m pip install watchdog Pillow
Execução:   py organizar_downloads.py
Sem janela: pyw organizar_downloads.py
Os arquivos existentes também são examinados ao iniciar.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import stat
import sys
import threading
import time
import warnings
import zipfile

from PIL import Image, UnidentifiedImageError
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


CATEGORIAS = {
    "Imagens": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"},
    "Documentos_PDF": {".pdf"},
    "Planilhas_Docs": {".xlsx", ".xls", ".csv", ".docx", ".doc", ".txt", ".pptx"},
    "Instaladores": {".exe", ".msi", ".iso"},
    "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Videos_Audios": {".mp4", ".mkv", ".avi", ".mp3", ".wav"},
}
DESTINOS = {ext: pasta for pasta, extensoes in CATEGORIAS.items() for ext in extensoes}
TEMPORARIOS = {".crdownload", ".tmp", ".part", ".partial", ".download"}
LOG = logging.getLogger("downloads")


def downloads_padrao() -> Path:
    """Consulta a Known Folder do Windows, inclusive Downloads redirecionada."""
    import uuid

    class GUID(ctypes.Structure):
        _fields_ = [("data", ctypes.c_ubyte * 16)]

    guid = GUID()
    guid.data[:] = uuid.UUID("374DE290-123F-4565-9164-39C4925E467B").bytes_le
    shell = ctypes.WinDLL("shell32")
    ole = ctypes.WinDLL("ole32")
    get_folder = shell.SHGetKnownFolderPath
    get_folder.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD,
                           wintypes.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
    get_folder.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole.CoTaskMemFree.restype = None
    ptr = ctypes.c_void_p()
    result = get_folder(ctypes.byref(guid), 0, None, ctypes.byref(ptr))
    try:
        if result != 0:
            raise OSError(f"SHGetKnownFolderPath falhou: HRESULT {result:#x}")
        return Path(ctypes.wstring_at(ptr))
    finally:
        if ptr.value:
            ole.CoTaskMemFree(ptr)


def configurar_logs(arquivo: Path) -> None:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    handlers = [RotatingFileHandler(arquivo, maxBytes=5_000_000,
                                    backupCount=3, encoding="utf-8")]
    # pythonw.exe não fornece terminal; o log em arquivo continua disponível.
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S", handlers=handlers)


def assinatura(caminho: Path) -> tuple[int, int, int, int]:
    info = caminho.lstat()
    if not stat.S_ISREG(info.st_mode) or caminho.is_symlink():
        raise FileNotFoundError("Não é um arquivo regular")
    return info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino


@contextmanager
def impedir_escrita(caminho: Path):
    """Bloqueia escrita durante a validação e permite renomear no Windows.

    FILE_SHARE_WRITE fica desabilitado: escritores existentes causam erro
    de compartilhamento e novos escritores aguardam uma próxima tentativa.
    """
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = create(str(caminho), 0x80000000, 0x1 | 0x4, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def verificar(caminho: Path) -> tuple[bool, str]:
    """Validação básica; não equivale a antivírus nem a checksum do servidor."""
    # PermissionError/OSError de acesso são tratados pelo agendador.
    with caminho.open("rb") as arquivo:
        if not arquivo.read(1):
            return False, "arquivo vazio (0 bytes)"
        arquivo.seek(0)
        if caminho.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(arquivo) as imagem:
                        imagem.verify()
                    # verify() sozinho não decodifica todos os pixels de JPEG.
                    arquivo.seek(0)
                    with Image.open(arquivo) as imagem:
                        imagem.load()
            except PermissionError:
                raise
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
                    Image.DecompressionBombError, Image.DecompressionBombWarning) as erro:
                return False, f"imagem inválida ou fora dos limites de segurança: {erro}"
        elif caminho.suffix.lower() == ".zip":
            if not zipfile.is_zipfile(arquivo):
                return False, "estrutura ZIP não reconhecida"
    return True, "verificação básica aprovada"


def mover_sem_sobrescrever(origem: Path, pasta: Path) -> Path:
    """No Windows, os.rename falha se o destino já existe, sem sobrescrever.

    Não usa shutil.move: seu fallback pode copiar/sobrescrever. Uma pasta em
    outro volume causa erro e preserva a origem, em vez de copiar parcialmente.
    """
    for indice in range(100_000):
        nome = origem.name if indice == 0 else f"{origem.stem}({indice}){origem.suffix}"
        destino = pasta / nome
        try:
            os.rename(origem, destino)
            return destino
        except FileExistsError:
            continue
    raise OSError("Limite de nomes duplicados atingido")


@dataclass
class Pendente:
    proxima: float = 0.0
    anterior: tuple[int, int, int, int] | None = None
    aviso: str = ""


class Organizador(FileSystemEventHandler):
    """Eventos apenas enfileiram; o laço principal verifica sem sleeps por arquivo."""

    def __init__(self, raiz: Path, estabilidade: float, destinos=None, quarentena=False,
                 stop_event=None, on_result=None):
        self.raiz = raiz
        self.estabilidade = estabilidade
        self.destinos = DESTINOS if destinos is None else destinos
        self.quarentena = quarentena
        self.stop_event = stop_event or threading.Event()
        self.on_result = on_result or (lambda kind, path: None)
        self.pendentes: dict[Path, Pendente] = {}
        self.lock = threading.Lock()

    def adicionar(self, nome: str | Path) -> None:
        caminho = Path(os.path.abspath(nome))
        if (caminho.parent != self.raiz or caminho.suffix.lower() in TEMPORARIOS
                or caminho.suffix.lower() not in self.destinos):
            return
        with self.lock:
            if caminho not in self.pendentes:
                self.pendentes[caminho] = Pendente()
                LOG.info("Detectado: %s", caminho.name)

    def on_created(self, evento):
        if not evento.is_directory:
            self.adicionar(evento.src_path)

    def on_modified(self, evento):
        if not evento.is_directory:
            self.adicionar(evento.src_path)

    def on_moved(self, evento):
        if not evento.is_directory:
            self.adicionar(evento.dest_path)

    def avisar(self, item: Pendente, mensagem: str) -> None:
        # Evita repetir o mesmo alerta a cada tentativa.
        if item.aviso != mensagem:
            LOG.warning(mensagem)
            item.aviso = mensagem

    def processar(self, caminho: Path, item: Pendente) -> bool:
        """Retorna True quando pode remover da fila; False agenda nova tentativa."""
        atual = assinatura(caminho)
        if atual != item.anterior:
            item.anterior = atual
            item.aviso = ""
            return False
        with impedir_escrita(caminho):
            # Confere novamente depois de adquirir o bloqueio contra escrita.
            if assinatura(caminho) != atual:
                item.anterior = None
                return False
            aprovado, motivo = verificar(caminho)
            if not aprovado:
                self.avisar(item, f"Mantido em Downloads: {caminho.name} — {motivo}")
                if self.quarentena:
                    destino = mover_sem_sobrescrever(caminho, self.raiz / "Quarentena_Corrompidos")
                    LOG.warning("Enviado para quarentena: %s", destino)
                    self.on_result("quarentena", destino)
                    return True
                item.proxima = time.monotonic() + 30
                return False
            if assinatura(caminho) != atual:
                item.anterior = None
                return False
            destino = mover_sem_sobrescrever(caminho, self.raiz / self.destinos[caminho.suffix.lower()])
            LOG.info("%s | %s | destino: %s", caminho.name, motivo, destino)
            self.on_result("movido", destino)
            return True

    def executar_pendentes(self) -> None:
        with self.lock:
            lote = list(self.pendentes.items())
        for caminho, item in lote:
            if self.stop_event.is_set():
                break
            if time.monotonic() < item.proxima:
                continue
            item.proxima = time.monotonic() + self.estabilidade
            remover = False
            try:
                remover = self.processar(caminho, item)
            except FileNotFoundError:
                remover = True  # Removido ou renomeado por outro programa.
            except PermissionError as erro:
                self.avisar(item, f"Aguardando liberação: {caminho.name} — {erro}")
                item.anterior = None
                item.proxima = time.monotonic() + 5
            except OSError as erro:
                self.avisar(item, f"Falha de acesso/movimentação: {caminho.name} — {erro}")
                item.anterior = None
                item.proxima = time.monotonic() + 30
            except Exception:
                LOG.exception("Falha inesperada ao processar %s; será tentado novamente", caminho)
                item.proxima = time.monotonic() + 30
            if remover:
                with self.lock:
                    self.pendentes.pop(caminho, None)

    def varrer(self) -> None:
        # Reconciliação periódica também cobre eventos perdidos pelo sistema.
        for caminho in self.raiz.iterdir():
            self.adicionar(caminho)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pasta", type=Path, help="Substitui a pasta Downloads do Windows")
    parser.add_argument("--estabilidade", type=float, default=2.0,
                        help="Segundos entre amostras de tamanho/data (padrão: 2)")
    parser.add_argument("--log", type=Path, help="Caminho alternativo para o arquivo de log")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("Este script requer Windows para garantir movimentação sem sobrescrita.")
    if not 1 <= args.estabilidade <= 60:
        parser.error("--estabilidade deve estar entre 1 e 60 segundos")
    log_padrao = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "OrganizadorDownloads" / "organizador.log"
    configurar_logs(args.log or log_padrao)
    observer = None
    try:
        raiz = (args.pasta or downloads_padrao()).resolve(strict=True)
        if not raiz.is_dir():
            raise NotADirectoryError(raiz)
        for categoria in CATEGORIAS:
            (raiz / categoria).mkdir(exist_ok=True)
        organizador = Organizador(raiz, args.estabilidade)
        observer = Observer()
        observer.schedule(organizador, str(raiz), recursive=False)
        observer.start()
        LOG.info("Monitorando %s | estabilidade: %.1fs | log: %s",
                 raiz, args.estabilidade, args.log or log_padrao)
        proxima_varredura = 0.0
        while observer.is_alive():
            if time.monotonic() >= proxima_varredura:
                try:
                    organizador.varrer()
                except OSError:
                    LOG.exception("Falha ao listar Downloads; nova tentativa em 30 segundos")
                proxima_varredura = time.monotonic() + 30
            organizador.executar_pendentes()
            time.sleep(0.25)
        LOG.error("O observador parou inesperadamente")
        return 1
    except KeyboardInterrupt:
        LOG.info("Encerramento solicitado")
        return 0
    except Exception:
        LOG.exception("Não foi possível manter o monitoramento")
        return 1
    finally:
        if observer is not None and observer.is_alive():
            observer.stop()
            observer.join()


if __name__ == "__main__":
    raise SystemExit(main())
