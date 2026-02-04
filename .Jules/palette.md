## 2026-02-04 - Accessible Button Groups
**Learning:** Custom button groups (divs with buttons) were used for radio-like selection without ARIA roles, making them inaccessible to screen readers.
**Action:** Always add `role="group"` (or `radiogroup`) to the container and manage `aria-pressed` (or `aria-checked`) on the buttons via JS.
