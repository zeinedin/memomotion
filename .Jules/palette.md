## 2024-05-22 - Accessibility of Custom Button Groups
**Learning:** Custom button groups acting as radio selectors often lack semantic state. Using `aria-pressed` on buttons within a `role="group"` is a low-friction way to provide feedback to screen readers without refactoring to native radio inputs or implementing full `radiogroup` keyboard handling (roving tabindex).
**Action:** When inspecting custom "toggle" UIs, first check for `aria-pressed` or `aria-checked` states. If missing, adding them + JS toggle logic is a high-value, low-risk micro-fix.
