## 2024-05-24 - Add accessible label to back button
**Learning:** Icon-only buttons (like a standard '✕' close button) often lack both screen-reader descriptions and mouse-hover context in web applications. Adding both `aria-label` and `title` solves this for multiple user groups simultaneously without altering the visual design.
**Action:** When adding `aria-label` to purely icon-based interactive elements, consistently add a `title` attribute as well to provide an immediate hover tooltip for sighted users.
