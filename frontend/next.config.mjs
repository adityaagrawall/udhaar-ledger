/**
 * Security headers.
 *
 * The CSP is built from the environment so it stays tight: only our own origin, the API,
 * and the Clerk frontend host decoded from the publishable key may be contacted.
 * Next.js emits small inline bootstrap scripts, so script-src keeps 'unsafe-inline'. This is an
 * accepted trade-off: the app renders no user-supplied HTML (React escapes everything), and a
 * nonce-based policy would force every page to render dynamically.
 */
const isProd = process.env.NODE_ENV === "production";

function clerkHost() {
  try {
    const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || "";
    const encoded = key.split("_").slice(2).join("_");
    const host = Buffer.from(encoded, "base64").toString("utf8").replace(/\$$/, "");
    return /^[a-z0-9.-]+$/i.test(host) ? `https://${host}` : "";
  } catch {
    return "";
  }
}

function origin(url) {
  try {
    return new URL(url).origin;
  } catch {
    return "";
  }
}

const apiOrigin = origin(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1");
const clerk = clerkHost();
const clerkSources = [clerk, "https://*.clerk.accounts.dev", "https://*.clerk.com"].filter(Boolean).join(" ");

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline' ${isProd ? "" : "'unsafe-eval'"} ${clerkSources} https://challenges.cloudflare.com`,
  "style-src 'self' 'unsafe-inline'",
  `img-src 'self' data: blob: https://img.clerk.com ${clerkSources}`,
  "font-src 'self' data:",
  // Clerk's bot-protection probes connect on non-default ports, so connect-src needs `:*` on its hosts.
  `connect-src 'self' ${apiOrigin} ${clerkSources} https://*.clerk.com:* https://*.clerk.accounts.dev:* https://clerk-telemetry.com`,
  `frame-src https://challenges.cloudflare.com ${clerkSources}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  isProd ? "upgrade-insecure-requests" : "",
]
  .filter(Boolean)
  .join("; ")
  .replace(/\s{2,}/g, " ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  ...(isProd ? [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" }] : []),
];

/** @type {import('next').NextConfig} */
const nextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  productionBrowserSourceMaps: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
