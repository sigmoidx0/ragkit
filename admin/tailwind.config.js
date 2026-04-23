/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Helvetica Neue", "Helvetica", "Arial", "system-ui", "sans-serif"],
      },
      colors: {
        brand: {
          50:  "#e6faf8",
          100: "#b3f0eb",
          200: "#80e6de",
          300: "#4fd1c5",
          400: "#38b2ac",
          500: "#2c9d97",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
