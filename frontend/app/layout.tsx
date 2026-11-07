import type { Metadata } from "next";
import { Fira_Sans, Fira_Code } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Providers from "@/components/Providers";
import DemoBanner from "@/components/DemoBanner";
import { clerkAppearance } from "@/lib/clerkAppearance";

const sans = Fira_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

const mono = Fira_Code({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Udhaar Ledger — Decision layer for distributor credit",
  description: "Ranked, explainable daily collection lists for Indian distributors and wholesalers.",
  icons: { icon: "/logo.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <ClerkProvider appearance={clerkAppearance} signInUrl="/login" signUpUrl="/sign-up" afterSignOutUrl="/login">
      <html lang="en" className={`${sans.variable} ${mono.variable}`}>
        <body className="min-h-screen bg-background text-foreground flex flex-col md:flex-row antialiased font-sans">
          <Providers>
            <Sidebar />
            <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
              <DemoBanner />
              {children}
            </main>
          </Providers>
        </body>
      </html>
    </ClerkProvider>
  );
}
