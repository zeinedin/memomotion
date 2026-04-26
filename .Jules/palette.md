## 2026-04-26 - Form Error Timeout UX
**Learning:** Automatically hiding form validation errors via a timeout (e.g., `setTimeout(() => clearError(), 2000)`) creates a frustrating UX, as users may miss the message or start fixing it just as it disappears. It also creates accessibility issues if screen readers miss the update.
**Action:** Form errors must persist until the user explicitly takes corrective action (e.g., an `input` event handler that clears the error state when they start typing).
