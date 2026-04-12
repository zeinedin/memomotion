## 2024-04-12 - Form Validation Interaction Design
**Learning:** Arbitrary timeouts on form validation errors (e.g., hiding error styling after 2000ms) create a frustrating user experience, especially for users relying on assistive technologies or those who need time to understand the error. Relying on `aria-invalid` provides better accessibility context.
**Action:** Always persist form error states until the user takes explicit action to correct the input (e.g., clear on the `input` event). Ensure the error message is semantically linked using `aria-errormessage` and `role="alert"`.
