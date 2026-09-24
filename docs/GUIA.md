# Download Studio

Aplicativo portátil para Windows 10/11 de 64 bits. Não precisa instalar Python.

1. Salve `DownloadStudio.exe` em uma pasta fixa, fora de Downloads.
2. Abra com dois cliques. Na primeira execução, o monitoramento começa pausado.
3. Confira a pasta na tela **Visão geral** e clique em **Iniciar organização**.
4. Para mudar regras, clique em **Pausar** e aguarde a operação atual terminar.

O aplicativo organiza também os arquivos já existentes na pasta selecionada.
Somente os arquivos na raiz são examinados; as subpastas não são percorridas.

## Telas

- **Visão geral:** escolher/abrir pasta, iniciar/pausar e acompanhar os contadores da sessão.
- **Categorias:** editar os nomes das seis pastas, as extensões e quais categorias ficam ativas.
  Separe extensões por vírgulas. Uma extensão só pode pertencer a uma categoria ativa.
- **Configurações:** tempo de estabilidade, quarentena opcional, início automático ao abrir
  o aplicativo, comportamento ao fechar e temas escuro/claro/sistema.
- **Atividade:** eventos e erros em tempo real, além de acesso ao log em disco.

Clique em **Salvar categorias** ou **Salvar configurações** após editar.
O botão **Iniciar organização** também valida e salva todas as configurações.

## Segundo plano

Por padrão, fechar a janela mantém o aplicativo na bandeja, perto do relógio.
Procure o ícone também entre os ícones ocultos do Windows. Dê dois cliques para
reabrir ou clique com o botão direito para iniciar/pausar ou **Sair**.

Minimizar a janela mantém a execução normalmente. A opção de iniciar ao abrir
se refere ao aplicativo; não instala inicialização automática no Windows.
Se desejar iniciar ao entrar no Windows, coloque um atalho do executável na
pasta aberta pelo comando `shell:startup` e ative a opção de monitoramento ao abrir.

## Arquivos e segurança da movimentação

Temporários de download são ignorados. O aplicativo espera estabilidade de tamanho
e data, testa leitura e impede escrita durante a verificação e movimentação.
PNG/JPG/JPEG são verificados com Pillow; ZIP recebe uma checagem estrutural;
os demais formatos precisam ser legíveis e ter tamanho maior que zero.

Duplicatas recebem sufixos como `arquivo(1).pdf`. Nenhum destino é sobrescrito.
Arquivos bloqueados são tentados novamente. Arquivos reprovados ficam na origem,
ou vão para `Quarentena_Corrompidos` se essa opção estiver ativada.

A estabilidade é uma heurística: programas que pausam e fecham um arquivo antes
de terminar o download podem exigir um intervalo maior. A verificação não equivale
a checksum completo nem antivírus; o ZIP não recebe teste de CRC de todas as entradas.
As categorias devem ser pastas comuns no mesmo volume, sem junções para outros discos.

## Configurações e logs

Ficam em `%LOCALAPPDATA%\DownloadStudio`:

- `config.json`: preferências salvas.
- `atividade.log`: histórico, com rotação de 5 MB e três backups.
- `erro-inicializacao.log`: diagnóstico se houver falha ao abrir.

Para remover o aplicativo, encerre pelo ícone da bandeja e exclua o executável.
Se quiser apagar as preferências, remova também a pasta de dados acima.
Os arquivos organizados permanecem nas respectivas categorias.

## Código-fonte e compilação

A pasta `app-source` contém o código modular e os testes. Para recompilar em
Windows x64, use Python 3.12 e uma pasta curta, por exemplo `C:\dev\DownloadStudio`:

```powershell
cd app-source
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_app.py
.\.venv\Scripts\python.exe build.py
```

O `build.py` gera `DownloadStudio.exe` na pasta acima de `app-source`. Interface
Qt/PySide6, monitoramento watchdog, validação Pillow e empacotamento PyInstaller.
O executável é portátil e não possui assinatura digital de editor.

