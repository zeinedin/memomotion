## 2024-05-22 - Semantic Grouping for Custom Controls
**Learning:** Custom button groups acting as radio/checkbox sets benefit significantly from `fieldset` + `legend` wrapping for screen reader context.
**Action:** Always check if a group of related controls (like difficulty or mode selectors) is wrapped in a generic `div`. If so, upgrade to `fieldset` and ensure `legend` is styled to match the previous label (often requiring `width: 100%` and `display: block/flex`).

## 2024-05-22 - State Management for Custom Toggles
**Learning:** Frontend UI controls are implemented as custom button groups using `role="group"`, requiring manual management of `aria-pressed` via JavaScript to indicate selection state.
**Action:** When adding interactive states to custom elements, ensure `aria-pressed` or `aria-checked` is updated in the corresponding event listener.
