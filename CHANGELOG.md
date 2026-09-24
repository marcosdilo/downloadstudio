# Histórico de versões

## 1.0.0 — 2026-09-24

Primeira versão do Download Studio para Windows x64.

- Interface Qt em português, com quatro telas e temas claro/escuro/sistema.
- Monitoramento watchdog com tratamento de criação, alteração e renomeação.
- Categorias editáveis, verificação básica, tentativas para bloqueios e proteção contra sobrescrita.
- Quarentena opcional, logs rotativos, contadores e preferências persistentes.
- Execução na bandeja, iniciar/pausar e proteção contra abertura duplicada.
- Executável portátil, código modular, documentação e testes de integração.

### Limitações conhecidas

- Estabilidade de escrita é uma heurística; integridade não é validada integralmente em todos os formatos.
- Categorias devem ser pastas comuns no mesmo volume.
- A primeira versão foi testada em Windows 11 x64; não possui assinatura digital.
- Não há atualizador automático, instalador ou registro automático na inicialização do Windows.
