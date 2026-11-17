# IslandToast

A notice that drops from the top as a pill and leaves the same way.

## Example

```tsx
import { IslandToast } from "./IslandToast";

<IslandToast message={notice} />
```

## Props

| Prop | Type | Default | What it does |
|---|---|---|---|
| message | string \| null |  | Set a text to show it; null hides it. You decide when. |
| icon | ReactNode | a check | Any icon; `null` for none. |

## Keyboard and screen readers

A status region: the message is announced.

## Notes

Place it once near the root, in a fixed layer.

Every colour comes from the `--fluid-*` variables, and the piece is yours to change.
