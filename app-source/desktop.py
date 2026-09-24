"""Download Studio: interface Qt, configurações e bandeja do Windows."""
import argparse
import ctypes
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import queue
import sys
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QPolygon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QCheckBox, QComboBox,
    QDoubleSpinBox, QStackedWidget, QScrollArea, QFrame, QPlainTextEdit,
    QFileDialog, QMessageBox, QSystemTrayIcon, QMenu)
import settings
from service import Monitor


def app_icon():
    pixmap = QPixmap(128, 128)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#172334"))
    p.drawRoundedRect(4, 4, 120, 120, 28, 28)
    p.setBrush(QColor("#20B99A"))
    p.drawRoundedRect(23, 68, 82, 31, 8, 8)
    p.setBrush(QColor("white"))
    p.drawRect(57, 25, 14, 45)
    p.drawPolygon(QPolygon([QPoint(42, 54), QPoint(86, 54), QPoint(64, 78)]))
    p.end()
    return QIcon(pixmap)


def label(text, role="", wrap=False):
    w = QLabel(text)
    w.setProperty("role", role)
    w.setWordWrap(wrap)
    return w


def button(text, callback, primary=False):
    w = QPushButton(text)
    w.setProperty("primary", primary)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.clicked.connect(callback)
    return w


def card():
    w = QFrame()
    w.setObjectName("card")
    box = QVBoxLayout(w)
    box.setContentsMargins(24, 20, 24, 20)
    box.setSpacing(12)
    return w, box


class UILog(logging.Handler):
    def __init__(self, events):
        super().__init__()
        self.events = events
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", "%H:%M:%S"))

    def emit(self, record):
        self.events.put(("log", self.format(record)))


class App(QMainWindow):
    def __init__(self, data_dir, smoke=False):
        super().__init__()
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.data_dir / "config.json"
        self.load_error = ""
        try:
            self.config = settings.load(self.config_path)
        except Exception as exc:
            self.config = settings.defaults()
            self.load_error = f"Não foi possível carregar as configurações: {exc}"
        self.events = queue.Queue()
        self.monitor = None
        self.closing = self.allow_close = False
        self.moved = self.quarantined = 0
        self.edit_widgets, self.category_rows = [], []
        self.setWindowTitle("Download Studio")
        self.setWindowIcon(app_icon())
        self.resize(1100, 800)
        self.setMinimumSize(920, 720)
        self.logger = logging.getLogger("downloads")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        disk = RotatingFileHandler(self.data_dir / "atividade.log", maxBytes=5_000_000,
                                   backupCount=3, encoding="utf-8")
        disk.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        self.log_handlers = [disk, UILog(self.events)]
        for handler in self.log_handlers:
            self.logger.addHandler(handler)
        self.build_ui()
        self.apply_theme()
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("Download Studio")
        menu = QMenu(self)
        menu.addAction("Abrir Download Studio", self.restore)
        menu.addAction("Iniciar / pausar", self.toggle)
        menu.addSeparator()
        menu.addAction("Sair", self.quit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.restore() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if not smoke and QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(100)
        if not smoke:
            if self.load_error:
                QTimer.singleShot(200, lambda: QMessageBox.warning(self, "Configurações", self.load_error))
            elif self.config["auto_start"]:
                QTimer.singleShot(400, self.start)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(215)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 32, 22, 26)
        side.setSpacing(10)
        side.addWidget(label("↓  DOWNLOAD", "brand"))
        side.addWidget(label("      S T U D I O", "muted"))
        side.addSpacing(30)
        self.nav = []
        self.titles = ["Visão geral", "Categorias", "Configurações", "Atividade"]
        for index, title in enumerate(self.titles):
            nav = button(title, lambda checked=False, i=index: self.show_page(i))
            nav.setCheckable(True)
            side.addWidget(nav)
            self.nav.append(nav)
        side.addStretch()
        side.addWidget(label("Tudo no seu computador", "smallbold"))
        side.addWidget(label("Seus arquivos ficam locais.\nVersão 1.0.0", "muted"))
        outer.addWidget(sidebar)
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(30, 28, 30, 22)
        body.setSpacing(20)
        head = QHBoxLayout()
        self.title_label = label("Visão geral", "title")
        head.addWidget(self.title_label)
        head.addStretch()
        self.status = label("●  Pausado", "badge")
        head.addWidget(self.status)
        body.addLayout(head)
        self.pages = QStackedWidget()
        body.addWidget(self.pages, 1)
        self.notice = label("Pronto. Escolha a pasta e inicie quando quiser.", "muted", True)
        body.addWidget(self.notice)
        outer.addWidget(content, 1)
        self.build_overview()
        self.build_categories()
        self.build_settings()
        self.build_logs()
        self.show_page(0)

    def page(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.pages.addWidget(widget)
        return layout

    def build_overview(self):
        page = self.page()
        hero, box = card()
        box.addWidget(label("Uma pasta leve. Tudo no lugar.", "hero"))
        box.addWidget(label("Organize seus downloads automaticamente, com verificação antes de mover.", "muted", True))
        box.addSpacing(12)
        box.addWidget(label("PASTA MONITORADA", "smallbold"))
        row = QHBoxLayout()
        self.folder = QLineEdit(self.config["folder"])
        row.addWidget(self.folder, 1)
        choose = button("Escolher", self.choose_folder)
        row.addWidget(choose)
        box.addLayout(row)
        self.edit_widgets.extend([self.folder, choose])
        controls = QHBoxLayout()
        self.start_btn = button("Iniciar organização", self.start, True)
        self.pause_btn = button("Pausar", self.pause)
        self.pause_btn.setEnabled(False)
        controls.addWidget(self.start_btn)
        controls.addWidget(self.pause_btn)
        controls.addStretch()
        controls.addWidget(button("Abrir pasta", self.open_folder))
        box.addLayout(controls)
        page.addWidget(hero)
        stats = QHBoxLayout()
        self.stats = {}
        for key, text in [("moved", "Organizados"), ("pending", "Em análise"), ("quarantine", "Em quarentena")]:
            tile, layout = card()
            number = label("0", "number")
            layout.addWidget(number)
            layout.addWidget(label(text, "muted"))
            stats.addWidget(tile, 1)
            self.stats[key] = number
        page.addLayout(stats)
        page.addWidget(label("Contadores desta sessão", "muted"))
        info, box = card()
        box.addWidget(label("Como funciona", "section"))
        box.addWidget(label("01   Aguarda a escrita terminar\n02   Verifica o arquivo\n03   Organiza sem substituir arquivos existentes", "muted"))
        page.addWidget(info)
        page.addWidget(label("Ao iniciar, os arquivos já existentes também serão organizados.", "muted", True))
        page.addStretch()

    def build_categories(self):
        page = self.page()
        page.addWidget(label("Defina o destino de cada extensão. Desative categorias que deseja ignorar.", "muted", True))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 10, 0)
        for category in self.config["categories"]:
            tile, box = card()
            row = QHBoxLayout()
            name = QLineEdit(category["name"])
            enabled = QCheckBox("Ativa")
            enabled.setChecked(category["enabled"])
            row.addWidget(name, 1)
            row.addSpacing(12)
            row.addWidget(enabled)
            box.addLayout(row)
            ext = QLineEdit(category["extensions"])
            ext.setPlaceholderText(".png, .jpg, .jpeg")
            box.addWidget(ext)
            layout.addWidget(tile)
            self.category_rows.append((name, ext, enabled))
            self.edit_widgets.extend([name, ext, enabled])
        layout.addStretch()
        scroll.setWidget(widget)
        page.addWidget(scroll, 1)
        save = button("Salvar categorias", self.save, True)
        page.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)
        self.edit_widgets.append(save)

    def build_settings(self):
        page = self.page()
        tile, box = card()
        box.addWidget(label("Monitoramento", "section"))
        row = QHBoxLayout()
        row.addWidget(label("Tempo de estabilidade (segundos)"), 1)
        self.stability = QDoubleSpinBox()
        self.stability.setRange(1, 60)
        self.stability.setSingleStep(0.5)
        self.stability.setValue(self.config["stability"])
        row.addWidget(self.stability)
        box.addLayout(row)
        self.edit_widgets.append(self.stability)
        for attr, text, key in [("quarantine", "Enviar arquivos reprovados para quarentena", "quarantine"),
                                ("auto_start", "Iniciar monitoramento ao abrir o aplicativo", "auto_start"),
                                ("close_tray", "Ao fechar a janela, continuar na bandeja", "close_to_tray")]:
            checkbox = QCheckBox(text)
            checkbox.setChecked(self.config[key])
            box.addWidget(checkbox)
            self.edit_widgets.append(checkbox)
            setattr(self, attr, checkbox)
        box.addSpacing(18)
        box.addWidget(label("Aparência", "section"))
        self.theme = QComboBox()
        self.theme.addItems(["Escuro", "Claro", "Sistema"])
        self.theme.setCurrentIndex(["Dark", "Light", "System"].index(self.config["theme"]))
        self.theme.currentIndexChanged.connect(self.apply_theme)
        box.addWidget(self.theme)
        self.edit_widgets.append(self.theme)
        box.addSpacing(18)
        box.addWidget(label("Proteção dos arquivos", "section"))
        box.addWidget(label("Duplicatas recebem um número no nome. A verificação é básica e não substitui um antivírus. "
                            "Sem quarentena, arquivos reprovados permanecem na pasta original.", "muted", True))
        page.addWidget(tile)
        row = QHBoxLayout()
        row.addWidget(button("Abrir dados e logs", lambda: self.open_path(self.data_dir)))
        row.addStretch()
        save = button("Salvar configurações", self.save, True)
        row.addWidget(save)
        self.edit_widgets.append(save)
        page.addLayout(row)
        page.addStretch()

    def build_logs(self):
        page = self.page()
        page.addWidget(label("Detecções, verificações e movimentações em tempo real.", "muted"))
        self.logbox = QPlainTextEdit()
        self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(1500)
        page.addWidget(self.logbox, 1)
        row = QHBoxLayout()
        row.addWidget(button("Limpar tela", self.logbox.clear))
        row.addStretch()
        row.addWidget(button("Abrir arquivo de log", lambda: self.open_path(self.data_dir / "atividade.log")))
        page.addLayout(row)

    def apply_theme(self):
        mode = self.theme.currentText()
        dark = mode == "Escuro" or (mode == "Sistema" and QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        bg, panel, sidebar, text, muted, border, btn = (
            ("#0D1623", "#172334", "#111D2D", "#E7EFFA", "#A2B1C5", "#2C3E55", "#26384D") if dark else
            ("#EDF2F7", "#FFFFFF", "#E3EAF3", "#172334", "#52647A", "#C9D5E3", "#DDE6F0"))
        self.setStyleSheet(f'''
            QWidget {{font-family: 'Segoe UI'; font-size: 13px; color: {text};}}
            QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{background: {bg};}}
            QFrame#sidebar {{background: {sidebar};}}
            QFrame#card {{background: {panel}; border-radius: 14px;}}
            QLabel {{background: transparent;}}
            QLabel[role="muted"] {{color: {muted};}}
            QLabel[role="title"] {{font-size: 28px; font-weight: 700;}}
            QLabel[role="hero"] {{font-size: 25px; font-weight: 700;}}
            QLabel[role="brand"] {{font-size: 19px; font-weight: 700;}}
            QLabel[role="section"] {{font-size: 17px; font-weight: 600;}}
            QLabel[role="smallbold"] {{font-size: 11px; font-weight: 600; color: {muted};}}
            QLabel[role="number"] {{font-size: 32px; font-weight: 700; color: #20B99A;}}
            QLabel[role="badge"] {{background: {panel}; border-radius: 12px; padding: 9px 18px; color: #20B99A;}}
            QPushButton {{background: {btn}; border: none; border-radius: 8px; padding: 11px 16px; font-weight: 600;}}
            QPushButton:hover {{border: 1px solid #20B99A; padding: 10px 15px;}}
            QPushButton[primary="true"], QPushButton:checked {{background: #20B99A; color: #08251E;}}
            QPushButton:disabled {{color: {muted}; background: {sidebar};}}
            QLineEdit, QDoubleSpinBox, QComboBox {{background: {bg}; border: 1px solid {border}; border-radius: 7px; padding: 9px;}}
            QLineEdit:focus, QDoubleSpinBox:focus {{border-color: #20B99A;}}
            QLineEdit:disabled {{color: {muted};}}
            QCheckBox {{spacing: 10px; padding: 8px 0;}}
            QCheckBox::indicator {{width: 19px; height: 19px; border-radius: 5px; border: 1px solid {border}; background: {bg};}}
            QCheckBox::indicator:checked {{background: #20B99A; border-color: #20B99A;}}
            QPlainTextEdit {{background: {panel}; border: 1px solid {border}; border-radius: 12px; padding: 12px; font-family: Consolas; font-size: 12px;}}
            QScrollArea {{border: none;}}
            QScrollBar:vertical {{background: {bg}; width: 10px;}}
            QScrollBar::handle:vertical {{background: {border}; border-radius: 5px; min-height: 25px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height: 0;}}
        ''')

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        self.title_label.setText(self.titles[index])
        for i, nav in enumerate(self.nav):
            nav.setChecked(index == i)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Escolher pasta para organizar", self.folder.text())
        if path:
            self.folder.setText(path)

    def open_path(self, path):
        try:
            os.startfile(Path(path).resolve(strict=True))
        except OSError as exc:
            QMessageBox.warning(self, "Abrir", str(exc))

    def open_folder(self):
        self.open_path(self.folder.text())

    def collect(self):
        config = {"folder": self.folder.text().strip(), "stability": self.stability.value(),
                  "quarantine": self.quarantine.isChecked(), "auto_start": self.auto_start.isChecked(),
                  "close_to_tray": self.close_tray.isChecked(),
                  "theme": ["Dark", "Light", "System"][self.theme.currentIndex()],
                  "categories": [{"name": n.text().strip(), "extensions": e.text().strip(), "enabled": v.isChecked()}
                                 for n, e, v in self.category_rows]}
        folder, _, _ = settings.validate(config)
        config["folder"] = str(folder)
        return config

    def save(self):
        if self.monitor and self.monitor.thread.is_alive():
            return False
        try:
            config = self.collect()
            settings.save(self.config_path, config)
            self.config = config
            self.notice.setText("Configurações salvas.")
            return True
        except (ValueError, OSError, KeyError) as exc:
            QMessageBox.warning(self, "Revise as configurações", str(exc))
            return False

    def set_editable(self, enabled):
        for widget in self.edit_widgets:
            widget.setEnabled(enabled)
        self.start_btn.setEnabled(enabled)
        self.pause_btn.setEnabled(not enabled)

    def start(self):
        if self.closing or (self.monitor and self.monitor.thread.is_alive()) or not self.save():
            return
        self.set_editable(False)
        self.status.setText("●  Iniciando")
        self.notice.setText("Pause o monitoramento para editar as configurações.")
        self.monitor = Monitor(self.config, self.events)
        self.monitor.start()

    def pause(self):
        if self.monitor and self.monitor.thread.is_alive():
            self.monitor.stop()
            self.status.setText("●  Pausando")
            self.pause_btn.setEnabled(False)
            self.notice.setText("Concluindo a operação atual antes de pausar…")

    def toggle(self):
        self.pause() if self.monitor and self.monitor.thread.is_alive() else self.start()

    def poll(self):
        for _ in range(250):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self.logbox.appendPlainText(value)
            elif kind == "state":
                self.status.setText("●  " + value)
                self.tray.setToolTip("Download Studio — " + value)
                if value in {"Pausado", "Erro"}:
                    self.set_editable(True)
                    self.stats["pending"].setText("0")
                    self.notice.setText("Monitoramento pausado. Você pode editar as configurações."
                                        if value == "Pausado" else "Monitoramento interrompido. Consulte a atividade.")
            elif kind == "pending":
                self.stats["pending"].setText(str(value))
            elif kind == "movido":
                self.moved += 1
                self.stats["moved"].setText(str(self.moved))
            elif kind == "quarentena":
                self.quarantined += 1
                self.stats["quarantine"].setText(str(self.quarantined))
            elif kind == "error":
                self.restore()
                QMessageBox.critical(self, "Monitoramento interrompido", value)

    def restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        elif self.config["close_to_tray"] and self.tray.isVisible() and not self.closing:
            self.hide()
            event.ignore()
        else:
            event.ignore()
            self.quit_app()

    def quit_app(self):
        if self.closing:
            return
        self.closing = True
        self.pause()
        self.notice.setText("Encerrando… aguarde a conclusão da operação atual.")
        self.finish_quit()

    def finish_quit(self):
        if self.monitor and self.monitor.thread.is_alive():
            QTimer.singleShot(100, self.finish_quit)
            return
        self.timer.stop()
        self.tray.hide()
        for handler in self.log_handlers:
            self.logger.removeHandler(handler)
            handler.close()
        self.allow_close = True
        self.close()
        QApplication.instance().quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--smoke-test", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    data_dir = args.data_dir or Path(os.environ["LOCALAPPDATA"]) / "DownloadStudio"
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    key = hashlib.sha256(str(data_dir.resolve()).casefold().encode()).hexdigest()[:24]
    mutex = kernel.CreateMutexW(None, False, "Local\\DownloadStudio-" + key)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(mutex)
        ctypes.windll.user32.MessageBoxW(None, "O aplicativo já está aberto. Procure o ícone na bandeja do Windows.", "Download Studio", 64)
        return
    try:
        qt = QApplication(sys.argv[:1])
        qt.setStyle("Fusion")
        qt.setQuitOnLastWindowClosed(False)
        app = App(data_dir, smoke=bool(args.smoke_test))
        if args.smoke_test:
            def smoke():
                try:
                    for index in range(4):
                        app.show_page(index)
                        qt.processEvents()
                    app.theme.setCurrentIndex(1)
                    app.theme.setCurrentIndex(0)
                    app.show_page(0)
                    app.ensurePolished()
                    app.grab().save(str(args.smoke_test.with_suffix(".png")))
                    args.smoke_test.write_text(json.dumps({"ok": True, "pages": 4,
                        "categories": len(app.category_rows), "frozen": bool(getattr(sys, "frozen", False))}), encoding="utf-8")
                except Exception as exc:
                    args.smoke_test.write_text(json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8")
                finally:
                    app.quit_app()
            QTimer.singleShot(400, smoke)
        else:
            app.show()
        qt.exec()
    finally:
        kernel.CloseHandle(mutex)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        if "--smoke-test" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, f"Não foi possível abrir Download Studio:\n{exc}", "Download Studio", 16)
        raise
