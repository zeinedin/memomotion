## 2024-03-01 - [Form Validation Feedback]
**Learning:** Automatically hiding form validation errors via a timeout (e.g., 2 seconds) is poor UX and inaccessible. Users may miss the error message, and screen readers may not have time to announce it. Furthermore, the error state on the input should persist until the user corrects the problem.
**Action:** Use an `input` event listener on form fields to explicitly clear the error state and `aria-invalid` attribute as soon as the user starts correcting the input, rather than relying on arbitrary timeouts.
