/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./templates/*.html",
    "./static/src/**/*.css",
    "./routers/**/*.py",
    "./main.py",
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require("daisyui")
  ],
};
