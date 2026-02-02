# Palette's Journal

## 2024-05-23 - Accessibility Attributes Conflict
**Learning:** Using `role="alert"` (which implies `aria-live="assertive"`) alongside `aria-live="polite"` creates a conflict. Screen readers may prioritize the role's implicit behavior or get confused.
**Action:** Use `role="alert"` for important errors (like form validation) without explicit `aria-live`, or use `role="status"` with `aria-live="polite"` for less urgent updates.
