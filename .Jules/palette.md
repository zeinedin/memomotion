## 2024-04-06 - Form Validation Accessibility & Persistence
**Learning:** Automatically clearing form errors with timeouts (e.g., `setTimeout` for 2s) creates a poor UX as the user may miss the error, and screen readers need persistent state markers like `aria-invalid`.
**Action:** Always persist form validation errors until the user manually corrects them (e.g., via the `input` event) and use `aria-errormessage`, `aria-invalid`, and `role="alert"` for robust accessibility.
