# Palette's Journal

## 2025-02-18 - Accessible Selectors via ARIA-Pressed
**Learning:** For custom button groups (like mode/level selectors) where visual design is strict, using `role="group"` with `aria-pressed` on buttons is a viable accessible pattern that maintains existing styles, though it requires manual state management in JS.
**Action:** When refactoring custom selectors, always pair `.active` class toggles with `aria-pressed="true/false"` updates.

## 2025-02-18 - Persistent Form Errors
**Learning:** Default browser behavior or simple timeouts for error clearing (e.g. removing red border after 2s) is poor UX. Errors should persist until the user takes action (e.g. types in the field).
**Action:** Add `input` event listeners to clear error messages and `aria-invalid` states immediately upon user interaction.
