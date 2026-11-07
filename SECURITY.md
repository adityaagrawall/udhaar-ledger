# Security

Udhaar Ledger is a portfolio project that handles only synthetic data. If you find a vulnerability (auth bypass, tenant data leak, secret exposure), please open a private security advisory on GitHub rather than a public issue.

Design notes: sign-in is Clerk-only, tokens are verified server-side against Clerk's JWKS, every query is scoped by organisation, and viewer accounts (including the public demo) are read-only on the server.
