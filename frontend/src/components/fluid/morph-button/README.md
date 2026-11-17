# MorphButton

A button that shrinks into a ball while it works and opens again with a check.

## Example

```tsx
import { MorphButton, type MorphButtonState } from "./MorphButton";

const [state, setState] = useState<MorphButtonState>("idle");

<MorphButton
  state={state}
  labels={{ idle: "Place order", loading: "Sending", done: "Order sent" }}
  onClick={async () => {
    setState("loading");
    await placeOrder();
    setState("done");
  }}
/>
```

## Props

| Prop | Type | Default | What it does |
|---|---|---|---|
| state | "idle" \| "loading" \| "done" |  | Drive it from your real request. |
| labels | { idle, loading?, done } | Send / Sending / Sent | The words for each state. |
| ...button props |  |  | Anything a `<button>` takes. |

## Keyboard and screen readers

`aria-busy` while loading, and a status region announces Sending and Sent.

## Notes

It stays on done until you set `state` back to idle.

Every colour comes from the `--fluid-*` variables, and the piece is yours to change.
