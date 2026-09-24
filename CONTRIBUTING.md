# Como contribuir

1. Abra uma issue descrevendo o problema ou a proposta.
2. Para código, faça um fork e crie uma branch para a alteração.
3. Prepare o ambiente Windows/Python 3.12 conforme o README.
4. Implemente a mudança mantendo interface, serviço e regras de arquivos separados.
5. Execute `python test_app.py` dentro de `app-source` usando o ambiente virtual.
6. Abra um pull request explicando a mudança, como foi validada e eventuais limitações.

## Cuidados ao desenvolver

- Use uma pasta temporária e arquivos de teste; não teste a movimentação em Downloads pessoais.
- Preserve a garantia de nunca sobrescrever um destino existente.
- Não adicione esperas ou operações longas à thread da interface.
- Não publique executáveis, ambientes virtuais, logs pessoais ou configurações locais no código.
- Ao alterar interface, inclua uma captura sem dados pessoais e verifique os dois temas.
- Ao alterar o empacotamento, teste o executável gerado, além do código Python.

## Relatar um problema

Informe versão do Windows, versão do aplicativo, passos para reproduzir e resultado esperado.
Se anexar logs, remova dados pessoais e nomes de arquivos sensíveis. Não anexe documentos
privados apenas para demonstrar uma falha; prefira um exemplo mínimo artificial.
