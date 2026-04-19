
## 2026-04-19 - Form Validation Accessibility
**Learning:** Form validation errors that disappear automatically via timeout fail accessibility requirements because screen reader users might not hear them or might lose context. Additionally, inputs need an `aria-errormessage` linking to a `role="alert"` element.
**Action:** Replaced timeout-based error clearing with event-driven clearing on `input`. Added `aria-errormessage`, `aria-invalid`, and `role="alert"` to create a robust accessible form validation pattern.
