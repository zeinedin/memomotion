## 2025-02-17 - Custom Button Groups Lacked ARIA
**Learning:** Frontend UI controls are implemented as custom button groups instead of native inputs, requiring manual ARIA state management (e.g., `aria-pressed`, `role="group"`).
**Action:** When working on UI controls in this project, always check for custom ARIA implementation on click handlers.
