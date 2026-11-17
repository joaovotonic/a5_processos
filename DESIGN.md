---
version: 1.0
name: a5-esteira-design-system
description: Design System oficial da Esteira de Produção A5 Tecnologia. Baseado no padrão Bento Glass + Blue Signature do VitrineBox com suporte nativo aos temas Claro e Escuro.
---

# Esteira A5 Tecnologia — DESIGN.md

Este documento define os tokens visuais, tipografia, geometria, movimento e regras de acesso do sistema **Esteira A5 Tecnologia** (`/admin`, `/diretoria`, `/tv`, `/os/<os>` e `/recepcao-fotos`).

## 1. Paleta de Cores (Claro Bento & Escuro Industrial)

### Tema Claro (Bento `#F5F5F7`)
| Token | Hex | Uso Principal |
| :--- | :--- | :--- |
| `--a5-bg` | `#F5F5F7` | Canvas principal da aplicação |
| `--a5-surface` | `rgba(255, 255, 255, 0.96)` | Cards elevados Bento, modais, sidebar/header glass |
| `--a5-surface-subtle` | `#EEF1F6` | Colunas Kanban, tiles internos `.bento-inner-tile` |
| `--a5-border` | `rgba(226, 232, 240, 0.92)` | Bordas sutis de cards, inputs e divisores |
| `--a5-text` | `#18181B` | Títulos e texto primário |
| `--a5-muted` | `#64748B` | Subtítulos, metadados e rótulos secundários |
| `--a5-primary` | `#3B82F6` / `#2563EB` | Ações principais, abas ativas, foco e highlights |

### Tema Escuro (Dark Bento `#09090B`)
| Token | Hex / RGBA | Uso Principal |
| :--- | :--- | :--- |
| `--a5-bg` | `#09090B` | Canvas escuro profundo |
| `--a5-surface` | `rgba(24, 24, 27, 0.92)` | Cards Bento translúcidos com `backdrop-blur` |
| `--a5-surface-subtle` | `#121216` | Colunas Kanban e tiles internos |
| `--a5-border` | `rgba(255, 255, 255, 0.08)` | Bordas sutis |
| `--a5-text` | `#F4F4F5` | Texto primário |
| `--a5-muted` | `#A1A1AA` | Texto secundário |
| `--a5-primary` | `#38BDF8` / `#3B82F6` | Acentos e indicadores ativos |

### Cores Semânticas
- Sucesso / Finalizada / Aprovado: `#10B981`
- Atenção / Aguardando / SLA: `#F59E0B`
- Urgente / Erro / Bloqueado: `#EF4444`
- Garantia / Destaque Técnico: `#8B5CF6`

## 2. Tipografia
- **UI Principal (`sans`):** `'Plus Jakarta Sans', system-ui, sans-serif`
- **Códigos de O.S., Pesos, Relógios e KPIs (`mono`):** `'JetBrains Mono', monospace` + `font-variant-numeric: tabular-nums`

## 3. Geometria, Motion & Drag-and-Drop
- **Cards Bento (`.modernize-card`):** `border-radius: 22px–24px`, `backdrop-filter: blur(12px)`, elevação sutil no hover.
- **Botões & Controles:** pílulas `rounded-full` com `MorphButton` em envios críticos e `CopyMorph` em cópia de textos/lacres.
- **Abas & Filtros:** `PillTabs` / `SegmentedPicker` (`@usefluid/motion`).
- **Toasts:** `IslandToast` flutuante no topo.
- **Drag-and-Drop:** `@dnd-kit` com `DragOverlay` elevado (`scale(1.03)`, `rotate(1.5deg)`) e slot listrado `.ember-hatch-blue`.

## 4. Regras de Acesso e Telas Públicas
- **`/login`:** Tela unificada de autenticação (`Priscila`, `Sr. Jacson`, `Master`).
- **`/admin`:** Exclusivo para `Priscila (Recepção)` e `Master`.
- **`/diretoria` (`/chamado`):** Exclusivo para `Sr. Jacson (Diretoria)` e `Master`.
- **`/tv` (`/painel-tv`), `/os/<os>`, `/recepcao-fotos`, `/etiqueta/<os>`:** Públicos (sem login) para operação direta da oficina.
