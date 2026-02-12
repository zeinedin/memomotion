# Palette's Journal - Critical Learnings

## 2024-05-22 - Initial Setup
**Learning:** Project uses vanilla HTML/CSS/JS in static folder.
**Action:** Focus on semantic HTML and ARIA attributes in static files.

## 2024-05-22 - Custom Toggle Groups
**Learning:** For custom "radio-like" button groups (where one must be active), using `role="group"` on the container and `aria-pressed` on the buttons is a pragmatic way to communicate state without implementing complex `role="radiogroup"` keyboard navigation (roving tabindex).
**Action:** Use `aria-pressed="true/false"` for exclusive toggle buttons when full radio semantics are too heavy.
