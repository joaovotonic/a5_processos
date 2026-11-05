# BASE DE CONHECIMENTO INSTITUCIONAL • A5 TECNOLOGIA
## Documento Mestre de Memória de Projeto, Engenharia de Software e Regras de Negócio

> **FINALIDADE DESTE DOCUMENTO:**
> Este documento é o repositório mestre de conhecimento institucional da **A5 Tecnologia** e do seu **Sistema Kanban Local de Manutenção e Metrologia de Balanças**. 
> Em qualquer nova sessão ou interação com o agente de IA Antigravity, **a leitura deste documento restaura 100% do contexto operacional, técnico, arquitetural e humano do projeto**, eliminando a necessidade de reaprendizado ou repetição de instruções pelo usuário.

---

## 1. SOBRE A EMPRESA: A5 TECNOLOGIA

* **Nome Comercial:** A5 Tecnologia (A5 Balanças & Sistemas / A5 Manaus).
* **Localização:** Manaus, Amazonas (AM) — Brasil.
* **Segmento de Atuação:** 
  - Venda, assistência técnica autorizada, manutenção eletromecânica, calibração e metrologia legal de instrumentos de pesagem comerciais e industriais.
  - Especialista e autorizada em balanças da marca **Toledo do Brasil (Linha Toledo Prix)**, além de marcas como Elgin, Filizola, Urano e Ramuza.
  - Atendimento a supermercados, frigoríficos, feiras, indústrias do Polo Industrial de Manaus (PIM), padarias, farmácias de manipulação e laboratórios.
* **Ambiente Regulatório e Metrologia:**
  - Sujeita às diretrizes e fiscalizações do **IPEM-AM (Instituto de Pesos e Medidas do Amazonas)** e do **INMETRO**.
  - Todo reparo em balança comercial/industrial exige aplicação de **Lacre Físico de Proteção** e aposição de **Selo de Equipamento Reparado do IPEM** com registro obrigatório de numeração.

---

## 2. ATORES DO SISTEMA E SUAS RESPONSABILIDADES

### 👤 1. Sr. Jacson (Diretoria / Liderança Executiva)
* **Papel:** Proprietário e Diretor da A5 Tecnologia.
* **Tomada de Decisão:** Define as diretrizes comerciais, aprova orçamentos críticos e monitora a produtividade da oficina.
* **Interfaces que Utiliza:**
  - `/diretoria`: Painel executivo exclusivo com indicadores de faturamento, lead time, ranking de produtividade e **Intercom com Voz Neural** para falar diretamente com o chão de fábrica.
  - `/apresentacao`: Demonstração comercial executiva passo a passo tela por tela para clientes VIP, investidores e auditorias.
  - Locução de chamadas: Consegue emitir comunicados sonoros em tempo real para a oficina através da Smart TV via sintetizador de voz (TTS).

### 👤 2. Priscila (Recepção / Atendimento de Balcão / Gestão de O.S.)
* **Papel:** Primeira linha de atendimento ao cliente no balcão e elo entre os clientes, o ERP Teorema e os técnicos de oficina.
* **Dispositivos que Opera:**
  - **Celular / Tablet no Balcão (`/recepcao`):** No momento em que o cliente chega, usa o smartphone para consultar o CNPJ na Receita Federal (busca em <1s), marcar os acessórios entregues, fotografar a balança e emitir na hora o Comprovante A4 preliminar estilo Teorema para o cliente assinar e levar.
  - **Computador da Recepção (`/admin`):** Opera o ERP Teorema (sistema contábil/fiscal da empresa) e o Painel Kanban da A5. Quando gera a O.S. oficial no Teorema, apenas vincula o número no Kanban. Isso despacha a balança para a Smart TV da oficina e abre a impressão da etiqueta térmica adesiva 60x40mm.
  - **Saída e Liberação:** Recebe alertas sonoros e visuais quando um técnico termina uma análise. Aplica o Selo Reparado do IPEM na balança na retirada do cliente e clica no botão com 1 clique para copiar o número do lacre direto para o Teorema ERP.

### 👤 3. Técnicos de Oficina (João e Equipe Técnica de Bancada)
* **Papel:** Diagnóstico, orçamento, substituição de peças, calibração de células de carga e teste de estufa térmica em placas lógicas.
* **Dispositivos que Operam:**
  - **Smartphones nas Bancadas (`/saida?os=<numero>`):** Operam exclusivamente pelo celular via Wi-Fi interno. O técnico aponta a câmera para a etiqueta adesiva na balança, lê o QR Code e a tela de bancada abre imediatamente com histórico, fotos da recepção e defeito relatado.
  - **Catálogo Digital Toledo Prix Integrado:** Ao elaborar o laudo, o técnico seleciona as peças com códigos oficiais da Toledo (placas, teclados, cabeças térmicas, células de carga) com preços já pré-calculados.
  - **Regra de Segurança de Orçamento:** Uma vez concluída a análise, o técnico não altera o orçamento por conta própria. Se precisar reabrir, clica em "Solicitar Reabertura", o que emite notificação para a Priscila aprovar no `/admin`.

---

## 3. ECOSSISTEMA DE SOFTWARE & HARDWARE

### A. O ERP Teorema e o Kanban A5
* O **Teorema ERP** é o sistema de gestão legado/oficial da A5, responsável pela emissão de notas fiscais, controle financeiro e geração da numeração sequencial legal das Ordens de Serviço.
* **O Problema Antigo:** O cliente ficava esperando em pé na fila da recepção enquanto a Priscila digitava tudo manualmente no Teorema para só então imprimir a folha de papel. Além disso, pranchetas e papéis sujos circulavam pela oficina, correndo risco de extravio, rasuras e perda de histórico.
* **A Solução Kanban A5:**
  1. A Priscila usa a **Pré-Entrada Inteligente (`/recepcao`)**: busca o CNPJ em <1s via BrasilAPI, tira fotos da balança, confere os acessórios e emite na hora o Comprovante Preliminar A4 idêntico ao modelo Teorema. O cliente assina e vai embora em menos de 2 minutos.
  2. O equipamento aguarda como **"Aguardando Teorema"** no Kanban (não polui a Smart TV da oficina com numerações provisórias).
  3. Com o cliente já liberado, Priscila abre o Teorema no PC, gera o número oficial da O.S., clica na pré-entrada no Kanban (`/admin`), digita o número gerado e confirma.
  4. Instantaneamente, a etiqueta térmica 60x40mm é gerada para colar no chassi da balança e o cartão digital é despachado para a Smart TV da oficina e liberado para os técnicos.

### B. Hardware e Impressão
1. **Impressora Térmica de Etiquetas (60x40mm):**
   - Marcas suportadas: Zebra (TLP 2844, GC420t, ZD220), Elgin (L42 Pro), Argox (OS-214 Plus), Bematech.
   - Padrão do layout: 60mm de largura por 40mm de altura, margens zeradas (`@page { size: 60mm 40mm; margin: 0; }`), alto contraste térmico, logotipo oficial A5, número de O.S. em destaque maciço ao lado do nome do cliente, grid 2x2 com caixas de acessórios recebidos (`[✓] Prato`, `[✓] Fonte`, `[✓] Cabo`, `[✓] Bateria`) e QR Code de alta precisão de 19mm.
2. **Impressora Padrão A4 (Laser / Jato de Tinta):**
   - Utilizada para o Comprovante de Pré-Entrada e Folha Digital de Orçamento (`@page { size: A4; margin: 8mm; }`).
3. **Smart TV 55" na Oficina (`/tv` e `/painel-tv`):**
   - Opera sem teclado ou mouse, com atualização automática em tempo real via WebSockets.
   - Exibe colunas de serviço, contadores de estufa térmica com barras de progresso, placar de balanças prontas com fanfarra sonora e rádio ambiente com YouTube e Audio Ducking automático.

---

## 4. ARQUITETURA TÉCNICA DO PROJETO

### Stack de Tecnologia
* **Linguagem:** Python 3.11+
* **Framework Web:** Flask 3.x
* **Comunicação em Tempo Real:** Flask-SocketIO (WebSockets + Engine.IO)
* **Banco de Dados:** SQLite3 com WAL mode (`journal_mode=WAL`), conexão com isolamento de transação e pool thread-safe (`kanban/database.py`).
* **Frontend:** HTML5 semântico, Tailwind CSS moderno (Clean Mode e Dark Mode Industrial), Vanilla JavaScript (sem frameworks pesados), SortableJS para Drag and Drop, Lucide Icons e QRCode.js.
* **APIs Externas:**
  - BrasilAPI (`https://brasilapi.com.br/api/cnpj/v1/{cnpj}`) para consulta instantânea e gratuita de dados cadastrais de pessoas jurídicas da Receita Federal.
  - ViaCEP para autocompletar endereços por CEP.
  - YouTube Streaming com suporte a Audio Ducking.

### Estrutura de Diretórios
```text
a5_kanban/
├── app.py                      # Ponto de entrada do servidor Flask e Socket.IO
├── kanban/                     # Módulo principal da aplicação
│   ├── config.py               # Configurações de caminhos, portas e diretórios de upload
│   ├── database.py             # DDL das tabelas, migrações e conexão SQLite segura
│   ├── realtime.py             # Eventos WebSocket (emit_board_updated, emit_admin_notification, etc.)
│   ├── utils.py                # Utilitários de rede (get_local_ip), datas e sanitização
│   ├── routes/
│   │   ├── cards.py            # API REST de cartões, pré-entradas, busca de CNPJ e clientes
│   │   ├── pages.py            # Rotas de páginas web (/admin, /tv, /saida, /recepcao, /diretoria, etc.)
│   │   ├── parts.py            # Rotas de catálogo de peças Toledo
│   │   └── youtube.py          # Streaming multimídia para a Smart TV
│   └── services/
│       ├── cards.py            # Lógica de negócio de ciclo de vida das O.S. e pré-entradas
│       ├── board.py            # Montagem das colunas do quadro Kanban e cálculo de lead time
│       ├── clients.py          # Serviço de busca de CNPJ, cache local e persistência de clientes
│       ├── parts.py            # Catálogo de peças e modelos Toledo Prix
│       └── backup.py           # Backup automático e dumps JSON do banco
├── templates/                  # Templates Jinja2 das telas do sistema
│   ├── admin.html              # Painel Kanban da Priscila & Gerência
│   ├── tv.html                 # Painel da Smart TV da Oficina
│   ├── saida.html              # Bancada Mobile dos Técnicos (Laudo & Catálogo Toledo)
│   ├── recepcao_fotos.html     # Pré-Entrada de Balcão com CNPJ, Fotos e Checklist
│   ├── comprovante_entrada.html# Espelho A4 da O.S. estilo Teorema para assinatura do cliente
│   ├── etiqueta.html           # Layout térmico oficial 60x40mm com QR Code
│   ├── folha_digital.html      # Prontuário técnico completo da O.S.
│   ├── diretoria.html          # Sala do Sr. Jacson com Intercom e métricas
│   ├── consulta.html           # Consulta rápida de balcão para vendedores
│   ├── gerencia.html           # Relatórios gerenciais e tempos médios
│   └── apresentacao.html       # Apresentação executiva comercial passo a passo
├── static/                     # Arquivos estáticos (CSS, JS, logos, screenshots, fotos)
│   ├── img/                    # Logotipos A5 e ícones
│   ├── img/screens/            # Capturas de tela reais de cada tela do sistema
│   ├── img/concept/            # Fotos conceituais em alta definição das bancadas e recepção
│   └── uploads/                # Armazenamento particionado de fotos de balanças por O.S.
└── tests/
    └── test_kanban.py          # Bateria completa de testes automatizados unitários e de integração
```

---

## 5. TABELAS DO BANCO DE DADOS (`kanban/database.py`)

1. **`clients`:**
   - `id`, `cnpj_cpf`, `client_name`, `trade_name`, `phone`, `email`, `address`, `city_state`, `created_at`, `updated_at`.
   - Armazena histórico cadastral de clientes para autocompletar instantâneo no balcão.
2. **`pending_entries`:**
   - Pré-registros criados no balcão antes da emissão oficial no Teorema.
   - `id`, `entry_protocol`, `cnpj_cpf`, `client_name`, `trade_name`, `phone`, `email`, `address`, `city_state`, `equipment_model`, `defect_reported`, `accessories_json`, `photos_json`, `status` ('pending' ou 'converted'), `converted_card_id`, `created_at`.
3. **`cards`:**
   - Ordens de Serviço ativas e arquivadas no Kanban.
   - `id`, `os_number`, `client_name`, `equipment_type`, `equipment_model`, `serial_number`, `defect_reported`, `entry_date`, `status` (coluna kanban), `technician`, `delivery_forecast`, `urgent`, `cnpj_cpf`, `trade_name`, `phone`, `email`, `address`, `city_state`, `accessories_json`, `parts_json`, `photos_json`, `total_parts_price`, `labor_price`, `total_price`, `old_seal_number`, `new_seal_number`, `ipem_seal_number`, `reopen_requested`, etc.
4. **`card_events`:**
   - Histórico de auditoria imutável (quem moveu o cartão, quando, qual status anterior e novo).
5. **`baking_timers`:**
   - Cronômetros de estufa térmica de placas em teste com notificação sonora ao zerar.
6. **`intercom_messages`:**
   - Mensagens da diretoria ou recepção com locução sonora nas caixas de som da oficina.

---

## 6. AS 7 TELAS DO SISTEMA (MAPA DE NAVEGAÇÃO)

| Nº | Rota | Nome da Tela | Usuário Principal | Objetivo Operacional |
|:---|:---|:---|:---|:---|
| **1** | `/recepcao` (ou `/recepcao-fotos`) | **Pré-Entrada Mobile & Fotos** | Priscila (Celular/Tablet) | Busca CNPJ na Receita Federal, tira fotos 360°, marca acessórios e gera Comprovante A4 para assinatura do cliente. |
| **2** | `/etiqueta/<os>` | **Etiqueta Térmica 60x40mm** | Priscila (Impressora Térmica) | Etiqueta adesiva com O.S. grande, nome do cliente, checklist de acessórios e QR Code para leitura rápida na bancada. |
| **3** | `/admin` | **Painel Kanban da Recepção** | Priscila & Gerência | Centro de comando: arrasta cartões, vincula O.S. do Teorema, autoriza reaberturas e monitora análises feitas. |
| **4** | `/saida?os=<os>` | **Bancada Mobile dos Técnicos** | Técnicos (Celulares) | Abre via QR Code, visualiza defeito/fotos, consulta catálogo de peças Toledo Prix e lança o orçamento técnico. |
| **5** | `/folha/<os>` | **Folha Digital de Orçamento** | Priscila / Técnico | Espelho digital completo com laudo, lista de peças substituídas, valores e histórico de intervenções técnicas. |
| **6** | `/tv` (ou `/painel-tv`) | **Painel Smart TV da Oficina** | Toda a Oficina (TV 55") | Visão contínua em tempo real de chamados, cronômetros de estufa, placar diário de balanças prontas e música YouTube com Ducking. |
| **7** | `/diretoria` | **Sala do Sr. Jacson** | Sr. Jacson (Diretoria) | Gestão estratégica, produtividade dos técnicos, backup com 1 clique e Intercom com locução de voz neural na oficina. |
| **Extra** | `/consulta` | **Consulta Rápida de Balcão** | Vendedores / Balcão | Busca instantânea por O.S., cliente ou número de série, com botão de cópia de lacre para o Teorema. |
| **Extra** | `/gerencia` | **Gerência & Métricas** | Gerência | Métricas de tempo de ciclo (lead time), curva ABC de peças e ranking mensal de balanças consertadas. |
| **Extra** | `/apresentacao`| **Apresentação Executiva** | Sr. Jacson & Clientes | Demonstração institucional passo a passo com fotos, mockups e visão de futuro da A5 Tecnologia. |

---

## 7. REGRAS DE NEGÓCIO E DECISÕES CRÍTICAS

1. **Autoridade Sequencial do Teorema:** O Kanban A5 **nunca inventa** números de O.S. oficiais para a oficina. Na entrada, gera apenas um protocolo provisório de balcão (`PRÉ-0001`). O número de O.S. oficial vem sempre do Teorema ERP, mantendo o controle fiscal e financeiro inviolável.
2. **Proteção da TV da Oficina:** Equipamentos em pré-entrada permanecem aguardando o número do Teorema e **não aparecem na Smart TV da oficina**, prevenindo qualquer confusão dos técnicos com ordens não oficializadas.
3. **Imutabilidade de Orçamentos Concluídos:** Quando o técnico finaliza um orçamento no celular, o cartão é travado e movido para `ANALISES FEITAS`. Qualquer edição posterior exige solicitação de liberação à Priscila.
4. **Sem Papel Sujo na Bancada:** A bancada do técnico é 100% digital via smartphone e QR Code. Nenhum técnico manipula papéis com graxa ou poeira de feira/frigorífico.
5. **Metrologia e Rastreabilidade IPEM:** O número do lacre físico colocado pelo técnico e o número do Selo IPEM colocado pela Priscila são registrados no sistema, com botão de cópia rápida para o Teorema e histórico permanente.
6. **Desativação do Sistema de Prateleiras:** Por decisão operacional da diretoria (Item 36 do Backlog), o sistema de localização física em prateleiras foi temporariamente desativado das interfaces para manter o foco na rapidez e simplicidade.
7. **Resiliência em Rede Local (Intranet):** O sistema opera em servidor local na A5. Se o link externo de internet oscilar, toda a oficina, balcão, bancadas e TV continuam operando normalmente sem interrupções.
8. **Chamados Externos, WhatsApp e Cloudflare Tunnel:** O planejamento de ponta a ponta para captura de chamados no grupo de WhatsApp da A5, triagem na recepção com O.S. do Teorema, despacho para a diretoria e acesso remoto seguro e gratuito via Cloudflare (`a5painel.online`) para o Sr. Jacson em Fortaleza está detalhado no documento mestre `PLANEJAMENTO_INTEGRACAO.md`.

---

## 8. COMANDOS ÚTEIS PARA O AMBIENTE

* **Iniciar o Servidor:** `python app.py` (Disponível em `http://127.0.0.1:5000` e no IP da rede local `http://192.168.100.10:5000`).
* **Executar a Suíte Completa de Testes:** `python -m unittest tests/test_kanban.py`
* **Testar Consulta de CNPJ no Terminal:**
  ```bash
  python -c "import urllib.request, json; res = urllib.request.urlopen('http://127.0.0.1:5000/api/cnpj/84083807000125'); print(json.loads(res.read().decode('utf-8')))"
  ```
* **Git Status e Sincronização:** `git status`, `git add .`, `git commit -m "..."`, `git push origin main`.

---
*Documento compilado e homologado pelo agente Antigravity para preservação perpétua de contexto da A5 Tecnologia.*

