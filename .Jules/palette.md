## 2025-02-12 - Custom Button Groups and ARIA Pressed
**Learning:** This app uses custom button groups for mode/level selection (`role="group"`). Since they are styled as buttons and not radio inputs, the standard `role="radiogroup"` pattern can be confusing if the interactive elements remain `<button>`. Using `aria-pressed` on the buttons to indicate the "selected" state (even for single-choice) provided a clear state for screen readers without breaking keyboard navigation or existing styles.
**Action:** When retrofitting accessibility onto custom button selectors, manual management of `aria-pressed` via JS is often the path of least resistance compared to rewriting them as native radio inputs.

## 2025-02-12 - Form Validation Feedback
**Learning:** The previous implementation used `setTimeout` to clear error states (red border), which is poor UX as users might miss the feedback if they look away.
**Action:** Always prefer clearing error states on user interaction (e.g., `input` event) rather than a timer. This gives the user control and ensures they see the error until they attempt to fix it.
