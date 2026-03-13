## 2024-05-24 - Missing ARIA Labels on Icon Buttons
**Learning:** Icon-only buttons without visible text (like the "✕" close button) need `aria-label` attributes for screen reader accessibility to explain their action contextually (e.g., "Quit game" instead of just "Close").
**Action:** Always verify icon-only buttons (`btn-icon` classes) have descriptive `aria-label`s.
