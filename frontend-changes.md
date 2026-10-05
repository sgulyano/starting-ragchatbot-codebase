# Frontend changes: dark/light theme toggle

## `frontend/index.html`
- Added a `#themeToggle` button (fixed, top-right) containing inline sun and moon SVG icons. Its `aria-label` is updated by JS to describe the action ("Switch to light/dark theme"); the icons are `aria-hidden`.
- Added a small inline `<script>` in `<head>` that reads `localStorage.theme` and sets `data-theme` on `<html>` before first paint, to prevent a flash of the wrong theme.
- Bumped the CSS/JS cache-busting query strings to `?v=11`.

## `frontend/style.css`
- Added a `:root[data-theme="light"]` block that overrides the existing CSS variables (background, surface, text, borders, primary, focus ring, welcome colors). Primary `#1d4ed8` on white and text `#0f172a` / `#475569` on light surfaces meet WCAG AA contrast.
- Moved previously hardcoded colors into new variables so both themes can set them: source-link colors, code/pre background, welcome shadow, error/success text, toggle icon color.
- Added `.theme-toggle` styles: 44px circular button matching the surface/border look, hover lift, visible `:focus-visible` ring, and a sun-to-moon rotate/fade icon animation.
- Added a `.theme-transition` rule that animates background, text, border and shadow colors for ~0.35s. It is disabled under `prefers-reduced-motion`.

## `frontend/script.js`
- Added `setupThemeToggle()` (called on `DOMContentLoaded`): toggles `data-theme` between `dark` (default) and `light` on `<html>`, persists the choice in `localStorage`, updates the button's `aria-label`, and adds `theme-transition` to `<html>` only for the duration of the switch.

## Accessibility
- The toggle is a native `<button>`, so it is keyboard-operable with Tab, Enter and Space, and has a visible focus ring.
