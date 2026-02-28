## 2024-05-24 - Form Validation Error UX/a11y Pattern
**Learning:** Form validation errors that auto-clear via timeouts (e.g., 2000ms) provide poor UX because they disappear before the user can fix the input, and fail accessibility standards for error identification.
**Action:** Always persist form validation errors until the user attempts to correct them (via the `input` event). Ensure errors use `role="alert"` (without `aria-live="polite"` to avoid screen reader conflicts) and tie the error state to the input field using `aria-invalid="true"`.
