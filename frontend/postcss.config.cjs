// Skip Tailwind/PostCSS when running Vitest to avoid native binding load in test env
const isTest = process.env.VITEST === "true";
module.exports = {
  plugins: isTest
    ? {}
    : {
        "@tailwindcss/postcss": {},
        autoprefixer: {},
      },
};

