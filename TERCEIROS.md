# Componentes

O aplicativo usa Python 3.12, Qt/PySide6 e Shiboken 6.11.2, watchdog 6.0.0,
Pillow 12.3.0 e o bootloader PyInstaller 6.22.3.

Qt/PySide6/Shiboken são utilizados sob LGPL versão 3. Os textos LGPL-3.0 e
GPL-3.0 estão em `licenses`. Os direitos autorais desses componentes pertencem
à The Qt Company Ltd. e aos respectivos colaboradores. Fontes e informações:

- https://code.qt.io/cgit/pyside/pyside-setup.git/
- https://code.qt.io/cgit/qt/qtbase.git/
- https://code.qt.io/cgit/qt/qtsvg.git/
- https://download.qt.io/official_releases/QtForPython/pyside6/
- https://download.qt.io/official_releases/qt/

O código-fonte do aplicativo e o script de compilação são fornecidos para
permitir modificação e reconstrução, inclusive com versões modificadas dessas
bibliotecas. Não há restrição adicional à engenharia reversa para depurar
modificações nas bibliotecas LGPL. As bibliotecas Qt são carregadas como DLLs
pelo executável empacotado. Para substituir componentes, ajuste as dependências
no ambiente de build e gere novamente o executável com `build.py`.

As licenças de Python, Pillow, watchdog e PyInstaller acompanham o código em
`licenses`. PyInstaller inclui exceção para distribuição do bootloader.

O código específico deste aplicativo pode ser usado, modificado e redistribuído
pelo destinatário, preservando os avisos e as licenças dos componentes de terceiros.
