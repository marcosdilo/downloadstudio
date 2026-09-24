"""Testes de integração em pastas temporárias, sem acessar Downloads reais."""
import copy
import json
from pathlib import Path
import queue
import tempfile
import time
import unittest
import zipfile
from PIL import Image
import settings
from service import Monitor
from core import impedir_escrita


def wait_for(predicate, timeout=12):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("Tempo de espera excedido")


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = settings.defaults()
        self.config["folder"] = str(self.root)
        self.config["stability"] = 1
        self.events = queue.Queue()
        self.monitor = None

    def tearDown(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.thread.join(10)
            self.assertFalse(self.monitor.thread.is_alive())
        self.tmp.cleanup()

    def start(self):
        self.monitor = Monitor(self.config, self.events)
        self.monitor.start()
        wait_for(lambda: (self.root / "Imagens").is_dir())

    def test_real_watcher_and_collisions(self):
        self.start()
        target = self.root / "Planilhas_Docs"
        (target / "arquivo.txt").write_text("antigo")
        temp = self.root / "arquivo.txt.crdownload"
        temp.write_text("novo")
        time.sleep(1.4)
        self.assertTrue(temp.exists())
        temp.rename(self.root / "arquivo.txt")
        wait_for(lambda: (target / "arquivo(1).txt").exists())
        self.assertEqual((target / "arquivo.txt").read_text(), "antigo")
        self.assertEqual((target / "arquivo(1).txt").read_text(), "novo")
        Image.new("RGB", (10, 10)).save(self.root / "foto.PNG")
        wait_for(lambda: (self.root / "Imagens/foto.PNG").exists())
        with zipfile.ZipFile(self.root / "dados.zip", "w") as z:
            z.writestr("texto.txt", "conteudo")
        wait_for(lambda: (self.root / "Compactados/dados.zip").exists())

    def test_quarantine_and_custom_category(self):
        self.config["quarantine"] = True
        self.config["categories"][2]["name"] = "Trabalho"
        self.start()
        (self.root / "ruim.png").write_bytes(b"nao e uma imagem")
        (self.root / "teste.txt").write_text("conteudo")
        wait_for(lambda: (self.root / "Quarentena_Corrompidos/ruim.png").exists())
        wait_for(lambda: (self.root / "Trabalho/teste.txt").exists())

    def test_invalid_and_locked(self):
        self.start()
        invalid = self.root / "ruim.png"
        invalid.write_bytes(b"invalido")
        empty = self.root / "vazio.txt"
        empty.touch()
        locked = self.root / "ocupado.txt"
        # Um escritor aberto faz o bloqueio de validação falhar.
        with locked.open("wb") as stream:
            stream.write(b"em download")
            stream.flush()
            time.sleep(2.5)
            self.assertTrue(locked.exists())
        wait_for(lambda: (self.root / "Planilhas_Docs/ocupado.txt").exists())
        self.assertTrue(invalid.exists())
        self.assertTrue(empty.exists())
        self.monitor.stop()
        self.monitor.thread.join(5)
        (self.root / "pausado.txt").write_text("permanece")
        time.sleep(1.2)
        self.assertTrue((self.root / "pausado.txt").exists())

    def test_config_validation_and_persistence(self):
        for name in ["../escape", "CON", "a/b", "Quarentena_Corrompidos"]:
            c = copy.deepcopy(self.config)
            c["categories"][0]["name"] = name
            with self.assertRaises(ValueError):
                settings.validate(c)
        c = copy.deepcopy(self.config)
        c["categories"][0]["extensions"] = ".pdf"
        with self.assertRaises(ValueError):
            settings.validate(c)
        p = self.root / "config.json"
        settings.save(p, self.config)
        self.assertEqual(settings.load(p), self.config)

    def test_disabled_category(self):
        self.config["categories"][0]["enabled"] = False
        self.monitor = Monitor(self.config, self.events)
        self.monitor.start()
        wait_for(lambda: (self.root / "Compactados").exists())
        Image.new("RGB", (8, 8)).save(self.root / "fica.png")
        time.sleep(2)
        self.assertTrue((self.root / "fica.png").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
