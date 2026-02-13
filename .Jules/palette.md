# Palette's Journal - Critical Learnings

## 2024-05-22 - Initial Setup
**Learning:** Project uses vanilla HTML/CSS/JS in static folder.
**Action:** Focus on semantic HTML and ARIA attributes in static files.

## 2024-05-22 - Accessible Toggle Groups
**Learning:** For custom "select one" button groups, `role="group"` with `aria-pressed` (toggled via JS) is a robust accessible pattern when full radio-group keyboard navigation isn't feasible.
**Action:** Ensure `aria-pressed` state is strictly mutually exclusive in JS for these groups.
