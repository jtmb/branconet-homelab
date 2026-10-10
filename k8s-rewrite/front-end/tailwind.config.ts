import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "hsl(240 10% 3.9%)",
        foreground: "hsl(0 0% 98%)",
        card: "hsl(240 10% 3.9%)",
        "card-foreground": "hsl(0 0% 98%)",
        popover: "hsl(240 10% 3.9%)",
        "popover-foreground": "hsl(0 0% 98%)",
        primary: "hsl(270 60% 50%)",
        "primary-foreground": "hsl(0 0% 98%)",
        secondary: "hsl(240 3.8% 10%)",
        "secondary-foreground": "hsl(0 0% 98%)",
        muted: "hsl(240 3.8% 10%)",
        "muted-foreground": "hsl(240 5% 64.9%)",
        accent: "hsl(270 60% 50%)",
        "accent-foreground": "hsl(0 0% 98%)",
        destructive: "hsl(0 62.8% 50.2%)",
        "destructive-foreground": "hsl(0 0% 98%)",
        border: "hsl(240 3.7% 10%)",
        input: "hsl(240 3.7% 10%)",
        ring: "hsl(270 60% 50%)",
      },
      borderRadius: {
        lg: "0.5rem",
        md: "calc(0.5rem - 2px)",
        sm: "calc(0.5rem - 4px)",
      },
      keyframes: {
        "tab-pop": {
          "0%":   { transform: "scale(1)",   filter: "brightness(1)" },
          "50%":  { transform: "scale(1.12)", filter: "brightness(1.4)" },
          "100%": { transform: "scale(1.08)", filter: "brightness(1.25)" },
        },
      },
      animation: {
        "tab-pop": "tab-pop 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) forwards",
      },
    },
  },
  plugins: [],
};

export default config;