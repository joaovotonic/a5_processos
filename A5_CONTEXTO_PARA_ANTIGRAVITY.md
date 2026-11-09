# A5 Processos — contexto para continuidade no Antigravity

Atualizado em 08/11/2026. Este documento resume o estado conhecido do sistema, as alterações recentes e os próximos passos para colocar o acesso remoto em funcionamento no PC da empresa.

## Resumo executivo

- Repositório: `joaovotonic/a5_processos`.
- A preparação de produção foi integrada e publicada em `main`.
- Commit publicado: `2bbb6f4` — `feat(producao): prepara acesso remoto protegido`.
- O usuário informou que o Git já está autenticado no PC da empresa.
- O túnel Cloudflare `a5-producao`, associado a `kanban.a5painel.cloud`, existe, mas a tela compartilhada mostrava **Inactive** e **0 active replicas**. Ainda falta instalar/iniciar o conector no PC da empresa.
- O token do Tunnel não foi recebido nem salvo nesta conversa. Nunca incluir o token em mensagens, arquivos do projeto, commits ou documentação.
- O PC da empresa ainda não foi atualizado ou testado nesta sessão.

## Alterações incluídas no commit

- `INICIAR_SERVIDOR.bat`: prepara o A5 e o Cloudflare Tunnel; verifica banco e pré-requisitos; gera e protege uma chave de sessão local; solicita o token do Tunnel na primeira execução e o guarda fora do repositório, em `%LOCALAPPDATA%\A5Processos\Cloudflare`; inicia o servidor e o Tunnel em janelas separadas.
- `app.py`, `kanban/config.py`, `kanban/__init__.py`: configuração de produção, Tunnel, Socket.IO/Gevent, cookies seguros, proxy reverso e endpoint `/healthz`.
- `kanban/routes/pages.py`, `templates/admin.html`, `templates/recepcao_fotos.html`: URL remota e tela móvel de pré-entrada de dados/fotos antes da criação da O.S. no Teorema.
- `templates/diretoria.html`: botões de chamada em ordem, com Técnico/ADM diferenciados, em maiúsculas e sem “TODA A OFICINA”; painel persistente com a rota finalizada abaixo do quadro.
- `INSTALAR_INICIALIZACAO_AUTOMATICA.bat`: instala atalhos para inicializar o servidor após o login da conta Windows.
- `README.md`, `requirements.txt` e testes atualizados.

## Validação realizada

- Suíte completa: **26 testes passaram**.
- `python -m compileall -q app.py kanban tests`: passou.
- `git diff --check`: passou.
- Configuração simulada de produção confirmou cookie `Secure` e Socket.IO no modo `gevent`.
- As dependências Gevent/WebSocket foram instaladas no Python desta estação para a validação. Isso não instala nada no PC da empresa.
- A branch de trabalho local estava limpa após o commit. A referência remota `origin/main` foi confirmada apontando para `2bbb6f49f116e4b3870775f8c456a8f1d32fc596`.

## Procedimento no PC da empresa

### Atualizar o código sem substituir o banco local

O PC já tem Git autenticado, segundo o usuário; portanto, não é necessário baixar ZIP se a pasta atual foi clonada com Git.

1. Fechar o servidor A5, se estiver aberto.
2. Na pasta atual do repositório, executar `ATUALIZAR_SISTEMA.bat`.
3. Digitar **2** para atualizar apenas o código e preservar o banco local. **Não pressionar Enter sem digitar**, pois o padrão do script é a opção 1, que atualiza também os dados do repositório.
4. Confirmar que o script terminou sem erros antes de prosseguir.
5. Se o sistema nessa máquina veio de um ZIP ou a pasta não for um repositório Git, parar e confirmar o procedimento antes de substituir arquivos.

### Iniciar o servidor e configurar o Tunnel

1. Executar `INICIAR_SERVIDOR.bat` na pasta atualizada.
2. Na primeira execução, obter o token do Tunnel no painel Cloudflare, no túnel `a5-producao`, em **Install cloudflared connector**. A tela mostrada pelo usuário já estava no túnel correto; selecionar **Windows** e **64-bit**.
3. Copiar o token longo que aparece após `cloudflared.exe service install` no comando do painel. Não é o PIN do Cloudflare Access e não é necessário executar o comando inteiro.
4. Colar o token apenas no prompt protegido do BAT. O token deve ficar salvo em `%LOCALAPPDATA%\A5Processos\Cloudflare\producao-token.txt`, fora do repositório.
5. Deixar abertas as janelas **A5 - Servidor** e **A5 - Cloudflare Tunnel**. O BAT abre o painel em `https://kanban.a5painel.cloud/admin`.
6. Confirmar que o Tunnel aparece ativo no painel Cloudflare e que o site abre através do Cloudflare Access. O primeiro acesso público ainda exige o fluxo Access configurado (PIN/e-mails autorizados).

O BAT verifica se existe `database\a5_kanban.db` e recusa iniciar em modo Tunnel se o banco não estiver presente. Também procura Python, instala Gevent/WebSocket se faltarem e tenta instalar `cloudflared` via `winget` caso não esteja disponível. Uma falha em qualquer pré-requisito deve ser corrigida antes de considerar o servidor no ar.

### Configurar início automático (opcional)

Após validar o início manual e o Tunnel:

1. Executar `INSTALAR_INICIALIZACAO_AUTOMATICA.bat` uma vez na conta Windows que deve hospedar o sistema.
2. Esse instalador cria um atalho na pasta Inicializar do usuário e atalhos na Área de Trabalho.
3. A configuração atual dispara **quando a conta entra no Windows**, não antes do login. O computador precisa estar ligado e conectado à Internet. Não foi configurada como serviço Windows.

## Segurança e preservação de dados

- Não compartilhar nem registrar o token do Tunnel em chats, commits, tickets ou arquivos Markdown.
- O token deve permanecer somente no arquivo local restrito criado pelo BAT. Se for exposto, revogá-lo/rotacioná-lo no Cloudflare e atualizar a cópia local.
- Escolher a opção 2 de atualização para preservar o banco de dados da empresa. É prudente confirmar que há backup recente antes de qualquer atualização.
- O banco e os backups locais da empresa não foram alterados durante esta sessão.
- Não executar `git reset --hard`, opção 1 do atualizador ou substituir a pasta inteira sem autorização e backup.

## Histórico relacionado

- Foram feitos ajustes da Diretoria solicitados pelo usuário: nomes em ordem João Otoni, Wisley, Guilherme, Arthur, Priscila, Roosevelt, Iago, Enzo, Edson e Antonio; separação visual Técnico/ADM; maiúsculas; remoção do botão geral; visualização da rota finalizada para Jacson.
- Foi incluída a tela de pré-entrada de fotos da recepção porque o link/QR anteriormente apontava para uma página inexistente.
- A prévia local usada durante o desenvolvimento foi encerrada. O servidor de teste não está rodando.
- Nenhum token foi coletado nesta conversa.

## Pontos que ainda precisam ser confirmados no PC

- A pasta do sistema é um clone Git e está na branch/código que deve ser atualizado.
- A atualização via opção 2 terminou sem erros e o banco local permaneceu intacto.
- O token foi cadastrado somente no prompt local do BAT.
- O conector Cloudflare ficou ativo e o site passou pelo Access corretamente.
- WebSockets e operação normal do A5 foram verificados de outro dispositivo/rede.
- Se desejado, o início automático foi configurado e testado após sair e entrar novamente na conta Windows.


## Correção no INICIAR_SERVIDOR.bat (09/11/2026)

- **Erro relatado**: `'"' não é reconhecido como um comando interno ou externo` e `ERRO: nao foi possivel gerar a chave de sessao` / `ERRO: a chave de sessao esta vazia ou invalida`.
- **Causa raiz**: Dentro do bloco `if not exist "%A5_SECRET_FILE%" (...)`, o CMD expande variáveis `%VAR%` em tempo de análise (parse time). Como a variável `%A5_PYTHON%` era definida e localizada dentro dos parênteses, na linha de execução ela era expandida para string vazia `""`, resultando no comando `"" -c ...` que falhava com o erro das aspas. Além disso, o comando `icacls` deletava o arquivo se retornasse erro em contas sem domínio padrão.
- **Solução implementada**:
  1. `call :find_python` foi movido para o escopo principal do script (fora de qualquer bloco de parênteses), garantindo que `%A5_PYTHON%` esteja sempre disponível.
  2. A geração e validação da chave de 64 caracteres hexadecimais foi delegada diretamente ao Python via script inline seguro, sem redirecionamento via `>` do CMD e sem criar arquivos corrompidos de 0 bytes.
  3. O `icacls` agora roda com supressão de erro e não destrói a chave caso o controle de herança falhe.
  4. Adicionado fallback para o executável `py` no buscador de Python.
