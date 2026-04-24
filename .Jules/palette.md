## 2024-05-24 - Persist Form Validation Errors
**Learning:** Form validation errors disappearing via a timeout creates a poor user experience and accessibility issue. They must persist until the user corrects the input, and ARIA attributes (like `aria-invalid`) must be managed explicitly alongside visual indicators.
**Action:** Use an 'input' event listener on form fields to clear error messages and reset invalid styles/attributes as the user types, rather than relying on a timeout.
