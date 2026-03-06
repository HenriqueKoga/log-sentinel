/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0B0F19",
        primary: "#7C3AED",
        accent: "#06B6D4",
      },
      borderRadius: {
        xl: "1rem",
      },
    },
  },
  plugins: [],
};

