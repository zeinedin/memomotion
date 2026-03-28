## 2026-03-28 - Persistent Form Validation Errors
**Learning:** Automatically hiding form validation errors after a timeout (e.g., 2 seconds) causes accessibility issues, particularly for screen reader users or users who take longer to process the information, as the error disappears before they can fix it.
**Action:** Always persist form validation errors until the user corrects the input (e.g., by clearing the error on the `input` event) and ensure the error state is properly linked using `aria-errormessage`, `role="alert"`, and `aria-invalid="true"`.
