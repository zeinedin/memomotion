## 2024-05-24 - Form Validation Error UX
**Learning:** Automatically hiding form validation errors (e.g., via a `setTimeout`) can be frustrating and inaccessible, as users may lose context before they can fix the error.
**Action:** Always persist form validation errors until the user directly interacts with the relevant input field (e.g., by listening for the `input` event and clearing the error/`aria-invalid` state then).
