## 2024-05-03 - Form Error A11y
**Learning:** Error messages in custom form fields currently lack ARIA connections to their corresponding inputs, making it difficult for screen reader users to understand validation failures.
**Action:** Link error messages to input fields using `aria-errormessage` and give error containers `role="alert"` (without `aria-live="polite"` to avoid conflicts).
