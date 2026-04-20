## 2024-05-24 - Accessibility Enhancements
**Learning:** Icon-only buttons lack context for screen reader users and elements without focus states make keyboard navigation impossible. Interactive elements must define clear `:focus-visible` styles using theme colors (like `--neon-cyan`) to preserve aesthetics without compromising a11y.
**Action:** Always verify icon-only interactive elements contain `aria-label` attributes and implement consistent `:focus-visible` states across the design system.
