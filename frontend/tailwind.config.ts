import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "sans-serif"],
      },
      colors: {
        brand: { DEFAULT: "#ef4444", dark: "#dc2626", glow: "rgba(239, 68, 68, 0.5)" },
        slate: {
          850: "#151e2e",
          950: "#0b0f19",
        }
      },
      animation: {
        "fade-in": "fadeIn 0.5s ease-out forwards",
        "float": "float 3s ease-in-out infinite",
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-5px)" },
        }
      }
    },
  },
  plugins: [],
};

export default config;
