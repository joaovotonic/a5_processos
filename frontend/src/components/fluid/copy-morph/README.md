# CopyMorph

A copy button where the two sheets flow into a check.

## Example

```tsx
import { CopyMorph } from "./CopyMorph";

<CopyMorph text="npm i @usefluid/motion" />
```

## Props

| Prop | Type | Default | What it does |
|---|---|---|---|
| text | string |  | What goes to the clipboard. |
| label | string | "Copy" | Accessible name. |
| doneLabel | string | "Copied" | Announced after copying. |
| done | boolean |  | Force the copied state, for showcases. |

## Keyboard and screen readers

A real button; the result is announced.

## Notes

Needs a secure context (https or localhost) for the clipboard.

Every colour comes from the `--fluid-*` variables, and the piece is yours to change.
