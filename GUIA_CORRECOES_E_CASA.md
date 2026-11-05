# 📋 Guia Completo de Correções, Diagnóstico de Erros e Passo a Passo para Casa
**Projeto:** Esteira de Produção & Rotas Externas — A5 Tecnologia (`joaovotonic/a5_processos`)  
**Usuário GitHub:** `joaovotonic` | **E-mail:** `joaovotoni1@gmail.com`

---

## 1. Diagnóstico do Erro de Backup no GitHub (`WinError 2`)

### ❌ O que aconteceu:
Ao clicar no botão **`☁️ Subir Banco de Dados p/ Nuvem (GitHub)`** na tela `/admin`, apareceu o alerta:
> `Erro ao executar backup no GitHub: [WinError 2] O sistema não pode encontrar o arquivo especificado`

### 🔍 Causa Raiz:
1. No Windows, o erro `[WinError 2]` dentro do `subprocess.run(["git", ...])` significa que o processo Python (`python app.py`) tentou chamar o comando `git`, mas a janela/terminal onde o Python estava rodando **não tinha a pasta `C:\Program Files\Git\cmd` carregada na variável `PATH`**.
2. Além disso, como o `app.py` roda em modo de produção (`debug=False`), quando alteramos um arquivo `.py` com o servidor já aberto, o processo antigo do Python na memória **não recarrega sozinho** até ser reiniciado (`Ctrl + C` e `python app.py`).

### ✅ Como foi corrigido no código (`kanban/backup.py`):
- Foi criada a função `_resolve_git_executable()` em `kanban/backup.py`, que procura automaticamente o executável `git.exe` nos caminhos padrões do Windows mesmo que o `PATH` não tenha sido carregado:
  - `C:\Program Files\Git\cmd\git.exe`
  - `C:\Program Files\Git\bin\git.exe`
  - `C:\Program Files (x86)\Git\cmd\git.exe`
  - `%LOCALAPPDATA%\Programs\Git\cmd\git.exe`
  - Git embutido do GitHub Desktop (`%LOCALAPPDATA%\GitHubDesktop\...\git.exe`)
- Também injetamos o diretório do `git.exe` no `PATH` dentro de `INICIAR_SERVIDOR.bat` e `ATUALIZAR_SISTEMA.bat`.

### 🛠️ O que fazer caso aconteça em casa ou no PC da Priscila:
1. Verificar se o **Git para Windows** está instalado (`https://git-scm.com/download/win`).
2. **Reiniciar o servidor Python** (`Ctrl + C` na janela do servidor e abrir novamente pelo `INICIAR_SERVIDOR.bat`).
3. Na **primeira vez** que o botão de backup for clicado em um PC novo, o Windows abrirá a janelinha do **Git Credential Manager** pedindo o login do GitHub (`joaovotonic`). Depois de logar 1 vez, o Windows salva a credencial para sempre.

---

## 2. Outros Problemas Resolvidos Nesta Sessão

### A) Consumo de PDFs nas Pastas (`entrada_pdfs` e `entrada_chamados_externos`)
- **Causa:**
  1. Quando uma O.S. de balança já existia no banco (vinda da importação do Trello), jogar o PDF dela em `entrada_pdfs` apenas atualizava os dados mas deixava o cartão escondido na coluna antiga. Agora o sistema **move o cartão para o topo de `ORÇAMENTOS`** e reseta o estágio para avaliação.
  2. Nos chamados externos (`entrada_chamados_externos`), o parser extraía a data de emissão antiga escrita dentro do PDF (ex: mês passado), fazendo o chamado não aparecer na rota de "Hoje". Agora o `pdf_watcher.py` força `route_date = data de hoje` ao consumir da pasta.
  3. Foi adicionada uma thread de varredura contínua a cada **1,5 segundo** (`PdfFoldersPollThread`) além do `watchdog` e de gatilhos diretos nas rotas `/api/board` e `/api/externos/orders`.

### B) Contabilização do Relatório do Sr. Jacson e Organização Manual da Priscila
- **Causa:**
  - O JSON exportado do Trello (`trelo_novo.json`) veio com diversas O.S. fora de ordem.
  - Quando a Priscila arrasta cartões antigos manualmente para organizar o Kanban (por exemplo, jogando O.S. antigas para `FINALIZADAS` ou `ORÇAMENTOS FEITOS`), o sistema registrava `finished_at = hoje` e `moved_at = hoje`, inflando erroneamente o relatório do Sr. Jacson (`/diretoria`).
- **Solução Implementada:**
  1. `move_card` (`kanban/services/cards.py`) agora sincroniza rigorosamente o `pipeline_phase` e os tempos de cada coluna.
  2. Criamos o arquivo **`INICIAR_CONTABILIZACAO_RELATORIO.bat`** e a função `reset_and_start_official_metrics()` (`kanban/services/diretoria.py`).
  3. Assim que a Priscila terminar de arrumar o Kanban à mão, basta ela dar 2 cliques em **`INICIAR_CONTABILIZACAO_RELATORIO.bat`**:
     - Todos os cartões permanecem exatamente nas colunas onde ela organizou;
     - Todos os contadores de **Balanças Prontas**, **Orçamentos Feitos**, **Ranking de Técnicos** e **Placar da TV** são zerados (`0`);
     - O banco grava o marco `metrics_start_at` e passa a contabilizar no relatório do Sr. Jacson **apenas o que for produzido dali para frente**.

### C) Visual e Impressão
- **Campo de busca do YouTube no modo claro (`/tv`)**: corrigido o fundo escuro (`#ytSearchInput` e `#ytSearchResultsWrap` em `templates/tv.html`) que deixava o texto invisível no tema `Clean`.
- **Badge `"Diagnóstico"` nos cartões (`/admin`)**: aumentado o contraste para leitura nítida no tema claro e escuro.
- **Etiqueta térmica 60x40mm (`/etiqueta/<os>`)**: removido o item `"Bateria"`, reduzido o QR Code para `15mm` (`56px`) e desagrupados os textos.
- **Diretoria (`/diretoria`)**:
  - Adicionado modal automático **"Ver Rota Pronta"** ao finalizar e liberar a rota;
  - Adicionado painel compacto **"Visão Rápida da Oficina (Tempo Real)"** com 3 colunas (*Para Orçamento*, *Técnicos na Bancada* e *Aprovados*).

---

## 3. Mapa dos Arquivos `.bat` Criados

| Arquivo `.bat` | Onde / Quando Usar | O que ele faz |
| :--- | :--- | :--- |
| **`INICIAR_SERVIDOR.bat`** | No PC da Priscila (ou em casa) | Inicia o servidor `app.py` na porta `5000`, abre o navegador em `/admin` e reinicia sozinho se cair. |
| **`INSTALAR_INICIALIZACAO_AUTOMATICA.bat`** | 1 única vez no PC da Priscila | Cria o atalho na pasta `shell:startup` do Windows para o servidor abrir sozinho ao ligar o PC. |
| **`ATUALIZAR_SISTEMA.bat`** | No PC da Priscila quando você mandar atualização | Protege o banco `a5_kanban.db` local da oficina, faz `git pull origin main` das suas alterações de código e atualiza dependências. |
| **`INICIAR_CONTABILIZACAO_RELATORIO.bat`** | No PC da Priscila após ela arrumar o Kanban à mão | Mantém a organização das colunas, zera os contadores antigos e inicia a contagem oficial do relatório do Sr. Jacson do zero. |

---

## 4. Passo a Passo para Você Fazer em Casa Hoje

### Passo 1 — Subir tudo do seu PC para o GitHub:
Abra o terminal na pasta do projeto e rode:
```powershell
git config user.name "joaovotonic"
git config user.email "joaovotoni1@gmail.com"
git add .
git commit -m "Sistema completo atualizado com banco Trello, scripts bat e backup em nuvem 16h40"
git push origin main
```

### Passo 2 — Testar o botão de Backup na Nuvem em casa:
1. Inicie o servidor pelo **`INICIAR_SERVIDOR.bat`** (ou `python app.py`).
2. Abra `http://localhost:5000/admin`.
3. Clique no botão **`☁️ Backup Nuvem`** no topo direito (ou no banner fixo das **16h40**).
4. Verifique se aparece a mensagem verde:
   `✅ Banco de dados salvo na nuvem GitHub (joaovotonic/a5_processos)!`

### Passo 3 — No PC da Priscila:
1. Instale o **Python** (marcando *"Add Python to PATH"*) e o **Git for Windows**.
2. Clone o repositório:
   ```powershell
   git clone https://github.com/joaovotonic/a5_processos.git
   cd a5_processos
   pip install -r requirements.txt
   ```
3. Dê 2 cliques em **`INSTALAR_INICIALIZACAO_AUTOMATICA.bat`**.
4. Dê 2 cliques em **`INICIAR_SERVIDOR.bat`**.
5. Deixe a Priscila organizar as O.S. fora de ordem no Kanban e, quando ela terminar, dê 2 cliques em **`INICIAR_CONTABILIZACAO_RELATORIO.bat`** para começar a contabilizar oficial para o Sr. Jacson!

