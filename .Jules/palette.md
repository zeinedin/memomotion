## 2024-05-23 - Custom Button Group Accessibility
**Learning:** The frontend uses custom button groups for mode/level selection without native radio semantics.
**Action:** Use `role="group"` on the container and manually manage `aria-pressed` on buttons via JS to convey selection state while maintaining native button keyboard navigation.
