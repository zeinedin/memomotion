## 2025-05-08 - Accessible and Persistent Form Validation
**Learning:** Implementing  and  tightly binds input fields to their respective error elements for screen readers. Form validation errors should persist until the user begins to correct them (e.g. typing) rather than disappearing on an arbitrary timeout, as timeouts can frustrate users if they didn't finish reading the error.
**Action:** Use the `input` event to clear error states rather than `setTimeout` to ensure users have enough time to read errors and the UI correctly reflects real-time correction attempts.
## 2025-05-08 - Accessible and Persistent Form Validation
**Learning:** Implementing `aria-invalid` and `aria-errormessage` tightly binds input fields to their respective error elements for screen readers. Form validation errors should persist until the user begins to correct them (e.g. typing) rather than disappearing on an arbitrary timeout, as timeouts can frustrate users if they didn't finish reading the error.
**Action:** Use the `input` event to clear error states rather than `setTimeout` to ensure users have enough time to read errors and the UI correctly reflects real-time correction attempts.
