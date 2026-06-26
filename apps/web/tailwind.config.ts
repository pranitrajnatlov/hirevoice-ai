import type { Config } from "tailwindcss";

// Light theme with purple and pink accents
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F8F6FA",
        surface: "#FFFFFF",
        border: "#E2E0E7",
        accent: { DEFAULT: "#6C48FF", soft: "rgba(108, 72, 255, 0.1)" },
        secondary: "#D62BA0",
        success: "#10b981",
        warn: "#f5a524",
        danger: "#ff8484",
        ink: { DEFAULT: "#111827", muted: "#6B7280" },
      },
      fontFamily: {
        sans: ["Inter", "SF Pro Display", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { xl: "16px", "2xl": "20px" },
      boxShadow: {
        glow: "0 0 20px rgba(108, 72, 255, 0.15)",
        card: "0 4px 20px rgba(0, 0, 0, 0.05)",
      },
      backdropBlur: { xs: "2px" },
      keyframes: {
        breathe: { "0%,100%": { transform: "scale(1)" }, "50%": { transform: "scale(1.04)" } },
        "pulse-ring": {
          "0%": { transform: "scale(0.95)", opacity: "0.7" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        breathe: "breathe 4s ease-in-out infinite",
        "pulse-ring": "pulse-ring 1.8s ease-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
