
## 2024-05-18 - Form Validation Feedback Lifecycles
**Learning:** Automatically clearing form validation errors (like red borders or error text) with a timeout (e.g., `setTimeout(..., 2000)`) is confusing UX because it signals the error is gone even if the user hasn't fixed it. It's also bad for accessibility as the visual state desyncs from the actual state.
**Action:** Always persist form validation errors until the user takes action to correct them (e.g., on the `input` event). When clearing the error state visually (removing borders/text), remember to explicitly reset the corresponding accessibility attributes like `aria-invalid="false"`.
