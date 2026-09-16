/** Tailwind ne scanne que le front React ; index.html ne contient que la coquille. */
module.exports = {
  content: ["./src/**/*.{js,jsx}", "../index.html"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: { sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"], mono: ["Geist Mono", "ui-monospace", "monospace"] },
      colors: {
        border: "hsl(var(--border))", input: "hsl(var(--input))", ring: "hsl(var(--ring))",
        background: "hsl(var(--background))", foreground: "hsl(var(--foreground))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
        popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
      },
      borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" },
      keyframes: {
        marquee: { from: { transform: "translateX(0)" }, to: { transform: "translateX(calc(-100% - var(--gap)))" } },
        shimmer: { "0%,90%,100%": { backgroundPosition: "calc(-100% - var(--shiny-width)) 0" }, "30%,60%": { backgroundPosition: "calc(100% + var(--shiny-width)) 0" } },
        "border-beam": { "100%": { offsetDistance: "100%" } },
        spotlight: { "0%": { opacity: 0, transform: "translate(-72%,-62%) scale(.5)" }, "100%": { opacity: 1, transform: "translate(-50%,-40%) scale(1)" } },
      },
      animation: {
        marquee: "marquee var(--duration) linear infinite",
        shimmer: "shimmer 8s infinite",
        "border-beam": "border-beam calc(var(--duration)*1s) infinite linear",
        spotlight: "spotlight 2s ease .75s 1 forwards",
      },
    },
  },
};
