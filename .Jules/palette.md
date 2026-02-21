## 2024-10-24 - Semantic Grouping for Button Sets
**Learning:** When using buttons as mutually exclusive options (like radio buttons), standard `role="radiogroup"` can be confusing if keyboard navigation isn't fully implemented (arrow keys). A simpler, robust pattern is `role="group"` with `aria-pressed` on the buttons. This maintains the native Tab navigation of buttons while clearly communicating the state to screen readers.
**Action:** Use `role="group"` + `aria-pressed` for custom toggle-sets instead of stripping button semantics or partially implementing complex ARIA widgets.
