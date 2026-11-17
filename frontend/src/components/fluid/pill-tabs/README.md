# PillTabs

Tabs with a pill that flows between them, and optional counts.

## Example

```tsx
import { PillTabs } from "./PillTabs";

<PillTabs label="Inbox" value={tab} onChange={setTab} tabs={[{ value: "new", label: "New", count: 3 }, { value: "all", label: "All" }]} />
```

## Props

| Prop | Type | Default | What it does |
|---|---|---|---|
| label | string |  | Accessible name of the tab list. |
| value | string |  | The current tab. |
| onChange | (value) => void |  |  |
| tabs | { value, label, count? }[] |  |  |

## Keyboard and screen readers

A tab list: arrow keys move between tabs. Give the panel below `role="tabpanel"`.

## Notes

For filters that do not switch panels, use SegmentedPicker.

Every colour comes from the `--fluid-*` variables, and the piece is yours to change.
