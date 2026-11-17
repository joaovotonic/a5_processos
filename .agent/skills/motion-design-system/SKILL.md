---
name: motion-design-system
description: Diretrizes de motion, física de mola e micro-interações para o sistema Esteira A5 Tecnologia (inspirado no VitrineBox MotionPrimitives/@usefluid/motion e taste-skill motion.md).
---

# Motion Design System — Esteira A5

Este guia unifica os padrões de movimento da SPA React (`motion/react`, `@usefluid/motion`, `@dnd-kit`) e das telas leves (`tv.html`, `os_tecnico.html`, `recepcao_fotos.html`).

## Curvas e Springs Oficiais
- **Easing principal:** `cubic-bezier(0.22, 1, 0.36, 1)` (`MOTION_EASE = [0.22, 1, 0.36, 1]`).
- **Snappy Spring:** `{ type: 'spring', stiffness: 420, damping: 32, mass: 0.85 }` para encaixe de cards, modais e drag-and-drop.
- **Fluid Tabs / Segmented / Toast:** `@usefluid/motion` (`PillTabs`, `SegmentedPicker`, `MorphButton`, `IslandToast`, `CopyMorph`).

## Regras de Interface Operacional
1. **Drag-and-Drop (`@dnd-kit`):** O cartão arrastado sobe para o `DragOverlay` com escala `1.03`, leve inclinação `1.5deg`, sombra profunda e borda azul iluminada; o slot de origem/destino exibe textura `.ember-hatch-blue`.
2. **Feedback tátil sem atraso:** Hover `120–180ms`, press `scale(0.985)`, contadores com `tabular-nums` (`CountUpValue`).
3. **Respeito à acessibilidade:** Sempre respeitar `prefers-reduced-motion: reduce` (`MotionConfig reducedMotion="user"` no React e media query no CSS).
4. **Exceção térmica:** `templates/etiqueta.html` (60x40mm) nunca recebe motion ou CSS decorativo.

Consulte `references/motion.md` para referências adicionais de micro-interações CSS/JS.
