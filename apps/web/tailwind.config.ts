import type { Config } from "tailwindcss";

// Dark Luxury theme — see docs/ARCHITECTURE.md "Design System".
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#071120",
        surface: "rgba(255,255,255,0.04)",
        border: "rgba(255,255,255,0.08)",
        accent: { DEFAULT: "#6C63FF", soft: "rgba(108,99,255,0.15)" },
        secondary: "#4CC9F0",
        success: "#00C896",
        warn: "#F5A524",
        danger: "#FF5C7A",
        ink: { DEFAULT: "#E8ECF4", muted: "#8A95A8" },
      },
      fontFamily: {
        sans: ["Inter", "SF Pro Display", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: { xl: "16px", "2xl": "20px" },
      boxShadow: {
        glow: "0 0 40px rgba(108,99,255,0.25)",
        card: "0 8px 40px rgba(0,0,0,0.35)",
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
