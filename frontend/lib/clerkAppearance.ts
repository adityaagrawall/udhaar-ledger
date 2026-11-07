/** Clerk components themed to match the Udhaar Ledger design tokens. */
export const clerkAppearance = {
  variables: {
    colorPrimary: "#1E3A8A",
    colorText: "#0B1330",
    colorTextSecondary: "#64748B",
    colorBackground: "#FFFFFF",
    colorInputBackground: "#FFFFFF",
    colorInputText: "#0B1330",
    colorDanger: "#E11D48",
    borderRadius: "0.75rem",
    fontFamily: "var(--font-sans), ui-sans-serif, system-ui, sans-serif",
    fontSize: "0.875rem",
  },
  elements: {
    card: "shadow-none border-0 p-0 bg-transparent",
    rootBox: "w-full",
    cardBox: "w-full shadow-none border-0 bg-transparent",
    header: "hidden",
    formButtonPrimary: "h-11 bg-brand-700 hover:bg-brand-600 text-sm font-semibold normal-case shadow-card",
    formFieldInput: "h-11 border-border",
    socialButtonsBlockButton: "h-11 border-border hover:bg-background",
    footer: "bg-transparent",
  },
} as const;
