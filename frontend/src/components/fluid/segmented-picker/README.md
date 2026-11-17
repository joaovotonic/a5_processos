# SegmentedPicker

Options in a row with a pill that flows to the chosen one.

## Example

```tsx
import { SegmentedPicker } from "./SegmentedPicker";

<SegmentedPicker
  label="Show"
  value={filter}
  onChange={setFilter}
  options={[
    { value: "all", label: "All" },
    { value: "active", label: "Active" },
    { value: "done", label: "Done" },
  ]}
/>
```

## Props

| Prop | Type | Default | What it does |
|---|---|---|---|
| label | string |  | Accessible name of the group. |
| value | string |  | The chosen option. |
| onChange | (value) => void |  |  |
| options | { value, label, ariaLabel? }[] |  | `label` can be any node, like a word and a count. |

## Keyboard and screen readers

A radio group: arrow keys move between options.

## Notes

Use it for filters and views of the same list. Under 480 px it fills the width and the options share it.

Every colour comes from the `--fluid-*` variables, and the piece is yours to change.
