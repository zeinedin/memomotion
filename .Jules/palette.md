## 2024-05-23 - Accessibility of Custom Button Groups
**Learning:** Frontend UI controls are implemented as custom button groups using `role="group"`, requiring manual management of `aria-pressed` via JavaScript to indicate selection state.
**Action:** When creating custom selection components, ensure `aria-pressed` or `aria-checked` is updated dynamically to reflect the visual `.active` state for screen reader users.
