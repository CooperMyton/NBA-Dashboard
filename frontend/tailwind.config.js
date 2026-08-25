/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Semantic tokens -> CSS variables defined in src/index.css (single source).
        bg: "var(--color-bg)",
        surface: "var(--color-surface)",
        "surface-2": "var(--color-surface-2)",
        border: "var(--color-border)",
        fg: "var(--color-fg)",
        "fg-muted": "var(--color-fg-muted)",
        accent: "var(--color-accent)",
        "accent-fg": "var(--color-accent-fg)",
        "accent-soft": "var(--color-accent-soft)",
        win: "var(--color-win)",
        loss: "var(--color-loss)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      boxShadow: {
        card: "0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 30px -16px rgba(0,0,0,0.7)",
      },
      borderRadius: {
        "2xl": "1.1rem",
      },
    },
  },
  plugins: [],
};
