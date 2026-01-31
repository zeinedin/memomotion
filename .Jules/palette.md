# Palette's Journal

## 2026-01-31 - Accessibility of Custom Radio Buttons
**Learning:** This app frequently uses standard `<button>` elements to create custom radio groups (Mode, Level, Filters), relying solely on the `.active` class for visual state. This leaves screen reader users unaware of the selected option.
**Action:** When observing custom selection components, check for `aria-pressed` or `aria-checked` attributes. If missing, they can often be added with minimal code changes alongside the class toggling logic.
