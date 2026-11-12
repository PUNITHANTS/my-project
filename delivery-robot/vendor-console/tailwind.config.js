import scrollbar from "tailwind-scrollbar";

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
      spacing: {
        13: "3.25rem", // topbar height
      },
      keyframes: {
        "pulse-once": {
          "0%, 100%": { boxShadow: "0 0 14px rgba(249,115,22,0.25)" },
          "50%":       { boxShadow: "0 0 22px rgba(249,115,22,0.55)" },
        },
      },
      animation: {
        "pulse-once": "pulse-once 0.6s ease 3",
      },
    },
  },
  plugins: [
    scrollbar({ nocompatible: true }),
  ],
};
