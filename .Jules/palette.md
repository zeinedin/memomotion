## 2026-03-22 - Accessible Custom Button Groups
**Learning:** When using custom button groups (like mode/level selectors) with `role="group"`, standard `aria-selected` is invalid. Screen readers require `aria-pressed` on the individual buttons to announce their toggle state correctly while preserving native tab navigation.
**Action:** Always pair `role="group"` container with `aria-pressed="true/false"` on child `<button>` elements, and ensure JavaScript syncs the ARIA state with the visual `.active` class.
