## 2024-05-17 - Persistent Form Validation
**Learning:** Automatically clearing form validation errors (like red borders) via timeouts confuses users and violates accessibility principles, as the screen reader's state (aria-invalid) and the visual state get out of sync or disappear before the user has a chance to correct the issue.
**Action:** Always persist form validation errors and `aria-invalid="true"` until the user actually corrects the input (e.g., by listening to the `input` event on the field), and properly link the error message using `aria-errormessage` and `role="alert"`.
