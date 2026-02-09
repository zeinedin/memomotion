# Palette's Journal - Critical Learnings

## 2024-05-22 - Initial Setup
**Learning:** Project uses vanilla HTML/CSS/JS in static folder.
**Action:** Focus on semantic HTML and ARIA attributes in static files.

## 2024-05-22 - Custom Toggle Groups
**Learning:** For custom button groups acting as exclusive selectors (like radio buttons), using `aria-pressed` on `<button>` elements is a valid pattern when full radio group keyboard behavior is not feasible.
**Action:** Always ensure `aria-pressed` state is updated via JS for these custom controls.
