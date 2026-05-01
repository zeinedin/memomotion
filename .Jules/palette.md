## 2024-12-04 - [Form Validation Persistence and Keyboard Focus]
**Learning:** Form validation errors should persist until the user corrects them rather than using arbitrary timeouts, and interactive elements require explicit `:focus-visible` states to support keyboard navigation.
**Action:** Linked error messages with `aria-errormessage`, applied `role="alert"`, implemented persistent validation states cleared on the `input` event, and added globally visible focus indicators using CSS variables.
