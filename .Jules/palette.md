# Palette's Journal - Critical Learnings

## 2024-05-22 - Initial Setup
**Learning:** Project uses vanilla HTML/CSS/JS in static folder.
**Action:** Focus on semantic HTML and ARIA attributes in static files.

## 2024-05-22 - Custom Toggle Groups
**Learning:** Frontend UI controls are implemented as custom button groups instead of native inputs, requiring manual ARIA state management (e.g., `aria-pressed`, `role="group"`).
**Action:** Always pair visual active classes with `aria-pressed` or `aria-checked` updates in JS event listeners for custom controls.
