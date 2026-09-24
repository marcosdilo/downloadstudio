# Arquitetura

## Módulos

| Módulo | Responsabilidade |
| --- | --- |
| `launcher.py` | Captura falhas de importação/inicialização e grava diagnóstico |
| `desktop.py` | Janelas Qt, preferências editáveis, bandeja e exibição dos eventos |
| `service.py` | Ciclo de vida do observador e thread de organização |
| `core.py` | Fila deduplicada, estabilidade, validação, bloqueio Windows e rename seguro |
| `settings.py` | Valores padrão, validação e gravação JSON por substituição do arquivo temporário |
| `build.py` | Ícone e build portátil com PyInstaller |

## Concorrência e encerramento

A interface roda na thread principal. O serviço roda em uma thread independente;
os callbacks do watchdog apenas adicionam arquivos à fila protegida por lock.
Uma fila de mensagens transmite estados, logs e contadores à interface, que a
consome por um timer Qt. Os callbacks do serviço não alteram widgets diretamente.

Pausar ou sair sinaliza um `threading.Event`. A operação de arquivo atual termina
antes do encerramento; a interface aguarda sem bloquear seu loop de eventos.
Configurações ficam desabilitadas durante a organização para evitar alterações
parciais nas regras em execução.

## Caminho de um arquivo

1. Extensões temporárias, desconhecidas ou desativadas são descartadas da fila.
2. Tamanho, data e identidade do arquivo são comparados em amostras separadas.
3. `CreateFileW` abre um handle que impede escrita e permite renomeação.
4. A assinatura é conferida novamente e o conteúdo recebe a validação básica.
5. `os.rename()` move no mesmo volume. No Windows, um destino já existente
   causa `FileExistsError`; o aplicativo tenta o próximo sufixo numérico.
6. Em caso de bloqueio ou erro transitório, o item permanece para nova tentativa.

Arquivos reprovados permanecem na origem ou são movidos para a quarentena,
conforme a configuração. Não existe exclusão automática de arquivos.

## Persistência e distribuição

Preferências e logs ficam em `%LOCALAPPDATA%\DownloadStudio`. Um mutex nomeado
impede duas instâncias com a mesma pasta de dados. O argumento `--data-dir`
permite isolar configurações em desenvolvimento.

O executável contém Python e as bibliotecas necessárias. O build remove outros
programas do `PATH` usado pelo empacotador, evitando a inclusão de DLLs externas
incompatíveis. Executáveis devem ser publicados como assets de uma Release.

## Escopo das garantias

O bloqueio impede escritores simultâneos durante a operação, mas não prevê um
programa que fecha o arquivo e pretende continuar a escrita mais tarde.
Não há garantia de integridade completa nem análise de malware. A aplicação
não funciona como serviço do Windows e depende da sessão do usuário.
