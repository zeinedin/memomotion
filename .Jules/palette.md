## 2024-06-17 - Add ARIA Labels and Title to Icon-Only Buttons
**Learning:** Icon-only buttons lacking ARIA labels or `title` attributes are a critical accessibility and UX issue, preventing screen readers from identifying the button's purpose and causing sighted users to guess its function.
**Action:** When adding `aria-label` to purely icon-only interactive elements, ensure to also add a `title` attribute to provide an immediate hover tooltip for sighted users.
