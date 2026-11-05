/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts,js,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Design tokens — overridden by CSS variables in tokens.css so the
        // values stay in one place.
        bg: {
          base: 'rgb(var(--c-bg) / <alpha-value>)',
          elev: 'rgb(var(--c-bg-elev) / <alpha-value>)',
          elev2: 'rgb(var(--c-bg-elev-2) / <alpha-value>)',
          elev3: 'rgb(var(--c-bg-elev-3) / <alpha-value>)',
        },
        fg: {
          DEFAULT: 'rgb(var(--c-fg) / <alpha-value>)',
          muted: 'rgb(var(--c-fg-muted) / <alpha-value>)',
          dim: 'rgb(var(--c-fg-dim) / <alpha-value>)',
        },
        border: {
          DEFAULT: 'rgb(var(--c-border) / <alpha-value>)',
          strong: 'rgb(var(--c-border-strong) / <alpha-value>)',
        },
        accent: {
          DEFAULT: 'rgb(var(--c-accent) / <alpha-value>)',
          hover: 'rgb(var(--c-accent-hover) / <alpha-value>)',
          dim: 'rgb(var(--c-accent-dim) / <alpha-value>)',
        },
        info: 'rgb(var(--c-info) / <alpha-value>)',
        success: 'rgb(var(--c-success) / <alpha-value>)',
        warn: 'rgb(var(--c-warn) / <alpha-value>)',
        danger: 'rgb(var(--c-danger) / <alpha-value>)',
        ct: 'rgb(var(--c-ct) / <alpha-value>)',
        t: 'rgb(var(--c-t) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
      },
      boxShadow: {
        elev1: '0 1px 2px rgba(0, 0, 0, 0.3), 0 0 0 1px rgb(var(--c-border) / 0.6)',
        elev2: '0 4px 12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgb(var(--c-border) / 0.6)',
        glow: '0 0 0 1px rgb(var(--c-accent) / 0.4), 0 0 16px rgb(var(--c-accent) / 0.25)',
      },
    },
  },
  plugins: [],
};
