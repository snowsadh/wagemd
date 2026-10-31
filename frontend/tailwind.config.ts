import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-manrope)", "sans-serif"],
        display: ["var(--font-pixelify)", "monospace"],
      },
      colors: {
        neutral: {
          50: "#faf7fa",
          100: "#f2edf3",
          200: "#ddc0d4",
          300: "#c6a8bc",
          400: "#80617a",
          500: "#6d5268",
          600: "#5c3f55",
          700: "#572747",
          800: "#3f1b36",
          900: "#2b1025",
        },
        signal: "#a21e5c",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
