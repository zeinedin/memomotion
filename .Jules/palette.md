## 2024-05-18 - Improve form validation error persistence
**Learning:** Form validation errors disappearing automatically via a timeout violates WCAG guidelines because it might not give users enough time to notice and understand the error. It also creates a frustrating experience if the user misses the message.
**Action:** Form validation errors should persist until the user corrects the input (e.g., clear on `input` event) rather than disappearing automatically.
