import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#ef4444", dark: "#b91c1c" },
      },
    },
  },
  plugins: [],
};

export default config;
