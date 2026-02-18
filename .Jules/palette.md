## 2024-05-22 - Custom Button Groups Accessibility
**Learning:** The application uses custom `div` containers with `<button>` elements and `.active` classes for radio-button-like selection (Mode/Level selectors). These lack semantic meaning for screen readers.
**Action:** When encountering this pattern, wrap the container in `role="group"` with an `aria-label`, and manually manage `aria-pressed` (or `aria-checked` if using `role="radiogroup"`) on the buttons via JavaScript to reflect the `.active` state.
