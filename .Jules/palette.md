
## 2024-05-18 - Persistent Error States for Accessibility
**Learning:** In MemoMotion, form validation errors (like the empty team name error) were previously cleared automatically using a `setTimeout` of 2 seconds. This auto-disappearing error violates accessibility guidelines as it may disappear before users, particularly those using screen readers, have time to comprehend and act upon it.
**Action:** When implementing validation feedback, avoid arbitrary timeouts. Instead, keep the error visible and ensure it persists. Clear the error only when the user takes a corrective action, such as interacting with the input field via an `input` event listener, and simultaneously manage the corresponding `aria-invalid` state.
