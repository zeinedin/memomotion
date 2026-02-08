# Palette's Journal - Critical Learnings

## 2024-05-22 - Initial Setup
**Learning:** Project uses vanilla HTML/CSS/JS in static folder.
**Action:** Focus on semantic HTML and ARIA attributes in static files.

## 2024-05-22 - Custom Toggle Groups
**Learning:** For custom button groups acting as exclusive selectors (like radio buttons but styled as buttons), `aria-pressed` can be used to indicate the active state if `role="radiogroup"` is not feasible due to keyboard navigation constraints.
**Action:** Ensure `aria-pressed` state is managed dynamically in JS alongside the visual `active` class.
