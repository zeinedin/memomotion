## 2024-05-22 - [Accessibility] Custom Button Groups
**Learning:** Frontend UI controls are implemented as custom button groups using `role="group"`, requiring manual management of `aria-pressed` via JavaScript to indicate selection state.
**Action:** When modifying selection logic, ensure `aria-pressed` attributes are updated alongside `.active` classes to keep semantic state in sync.
