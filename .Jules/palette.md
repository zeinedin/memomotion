## 2024-05-23 - Accessibility of Custom Radio Buttons
**Learning:** Custom buttons acting as radio selectors (mutually exclusive options) require `role="radio"` and explicit `aria-checked` state management. Native `<button>` elements are focusable but don't communicate "selected" state implicitly.
**Action:** When using custom UI for selection, always implement ARIA roles and update state via JS, or wrap native radio inputs visually hidden.
