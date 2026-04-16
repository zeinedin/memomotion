## 2024-05-15 - Improve Keyboard Accessibility & Icon Buttons
**Learning:** Icon-only buttons lacking `aria-label` are completely inaccessible to screen readers. Interactive elements require explicit `:focus-visible` styles using high-contrast design tokens to support robust keyboard navigation.
**Action:** Always add descriptive `aria-label` to icon-only buttons (like `#backToStartBtn`) and ensure all interactive elements (`.btn`, `.mode-btn`, `.level-btn`, `.filter-btn`) have consistent `:focus-visible` outlines.
