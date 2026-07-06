/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html"],
  theme: {
    extend: {
      colors: {
        // Driven by Telegram theme params (see assets/tailwind.css) with fallbacks.
        surface: "var(--surface)",
        card: "var(--card)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-ink)",
      },
      boxShadow: { card: "0 1px 2px rgba(0,0,0,.05), 0 10px 30px -14px rgba(0,0,0,.25)" },
    },
  },
  plugins: [],
};
