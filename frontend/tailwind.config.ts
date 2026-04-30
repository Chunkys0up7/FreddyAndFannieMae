import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./hooks/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        fannie: {
          DEFAULT: "#0033A0",
          light: "#E6EDF8",
        },
        freddie: {
          DEFAULT: "#00754A",
          light: "#E6F2EC",
        },
      },
    },
  },
  plugins: [],
};

export default config;
