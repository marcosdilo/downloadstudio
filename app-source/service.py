"""Monitoramento em thread independente; a interface recebe eventos por fila."""
import logging
import threading
import time
from core import Organizador
from watchdog.observers import Observer
from settings import validate

LOG = logging.getLogger("downloads")


class Monitor:
    def __init__(self, config, events):
        self.config = config
        self.events = events
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name="organizador", daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def run(self):
        observer = None
        failed = False
        try:
            folder, delay, mapping = validate(self.config)
            for name in set(mapping.values()):
                (folder / name).mkdir(exist_ok=True)
            if self.config["quarantine"]:
                (folder / "Quarentena_Corrompidos").mkdir(exist_ok=True)
            handler = Organizador(folder, delay, mapping, self.config["quarantine"],
                                  self.stop_event,
                                  lambda kind, path: self.events.put((kind, str(path))))
            observer = Observer()
            observer.schedule(handler, str(folder), recursive=False)
            observer.start()
            self.events.put(("state", "Ativo"))
            LOG.info("Monitoramento iniciado: %s", folder)
            scan = 0
            while not self.stop_event.is_set():
                if not observer.is_alive() or not all(e.is_alive() for e in observer.emitters):
                    raise RuntimeError("O observador do Windows parou. Pause e inicie novamente.")
                if time.monotonic() >= scan:
                    try:
                        handler.varrer()
                    except OSError:
                        LOG.exception("Não foi possível listar a pasta; nova tentativa em 30s")
                    scan = time.monotonic() + 30
                handler.executar_pendentes()
                with handler.lock:
                    self.events.put(("pending", len(handler.pendentes)))
                self.stop_event.wait(0.25)
        except Exception as exc:
            failed = True
            LOG.exception("Monitoramento interrompido")
            self.events.put(("error", str(exc)))
        finally:
            if observer is not None:
                observer.stop()
                if observer.ident is not None:
                    observer.join()
            LOG.info("Monitoramento encerrado")
            self.events.put(("state", "Erro" if failed else "Pausado"))
