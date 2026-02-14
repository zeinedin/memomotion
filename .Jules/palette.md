## 2024-05-24 - Custom Button Groups
**Learning:** The frontend uses `<div>` containers with `<button>` elements for mode/level selection, relying on CSS classes for state.
**Action:** Use `role="group"` on the container and manage `aria-pressed` on buttons via JS to make these accessible as toggle groups.
