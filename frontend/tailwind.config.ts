import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#F4F6FB",
        foreground: "#0B1330",
        // Ink-indigo: the "ledger ink" primary
        brand: {
          50: "#EFF3FF",
          100: "#DDE6FF",
          200: "#BDCDFF",
          300: "#93AAFB",
          400: "#6683F0",
          500: "#3B5CDB",
          600: "#2B49BD",
          700: "#1E3A8A",
          800: "#172B69",
          900: "#101C47",
          950: "#0B1330",
        },
        // Saffron: highlights, CTAs, "cleared" tick
        accent: {
          50: "#FFFBEB",
          100: "#FEF3C7",
          200: "#FDE68A",
          300: "#FCD34D",
          400: "#FBBF24",
          500: "#F59E0B",
          600: "#D97706",
          700: "#B45309",
        },
        ink: {
          DEFAULT: "#0B1330",
          900: "#0B1330",
          800: "#121B3D",
          700: "#1A2550",
          600: "#26325F",
        },
        sidebar: {
          DEFAULT: "#0B1330",
          surface: "#121B3D",
          hover: "#18234D",
          border: "#1C2751",
          muted: "#8E9BC7",
        },
        border: {
          DEFAULT: "#E3E8F2",
          light: "#EEF1F8",
          dark: "#CBD3E4",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(11, 19, 48, 0.04)",
        card: "0 1px 3px 0 rgba(11, 19, 48, 0.06), 0 1px 2px -1px rgba(11, 19, 48, 0.04)",
        elevated: "0 8px 24px -8px rgba(11, 19, 48, 0.14), 0 2px 6px -2px rgba(11, 19, 48, 0.06)",
        dropdown: "0 14px 32px -10px rgba(11, 19, 48, 0.22), 0 4px 8px -4px rgba(11, 19, 48, 0.08)",
        glow: "0 0 0 1px rgba(251, 191, 36, 0.35), 0 8px 24px -6px rgba(245, 158, 11, 0.35)",
      },
      backgroundImage: {
        "ledger-grid":
          "linear-gradient(to right, rgba(59,92,219,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(59,92,219,0.06) 1px, transparent 1px)",
        "hero-ink": "radial-gradient(1200px 500px at 85% -10%, rgba(59,92,219,0.45), transparent 60%), linear-gradient(160deg, #0B1330 0%, #101C47 100%)",
      },
    },
  },
  plugins: [],
};
export default config;
