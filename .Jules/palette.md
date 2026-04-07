## 2024-05-24 - Form Error Validation Lifecycle
**Learning:** Removing arbitrary timeouts (e.g. 2s) on form errors prevents users from losing context. Clearing the visual and semantic error state immediately upon the `input` event (when the user starts correcting) provides a much smoother and more responsive UX than waiting for a submit event or a timeout.
**Action:** Always link form inputs to error spans using `aria-errormessage`, apply `aria-invalid` to the input, and clear these states on the `input` event rather than using `setTimeout`.
