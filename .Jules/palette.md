## 2024-05-22 - Pragmatic Accessibility for Custom Selectors
**Learning:** For custom "select one of many" UI components implemented as buttons, adding `role="group"` and managing `aria-pressed` is a high-impact, low-risk accessibility improvement compared to a full refactor to `role="radiogroup"`.
**Action:** Use `aria-pressed` for button groups where visual design dictates button-like behavior, but ensure the container has a clear label.
