"use client";

import { SignUp } from "@clerk/nextjs";
import AuthShell from "@/components/AuthShell";

export default function SignUpPage() {
  return (
    <AuthShell>
      <h1 className="text-2xl font-semibold tracking-tight text-ink-900">Create your account</h1>
      <p className="mt-1 mb-6 text-sm text-slate-500">New accounts start with read-only access.</p>
      <SignUp routing="path" path="/sign-up" signInUrl="/login" fallbackRedirectUrl="/" />
    </AuthShell>
  );
}
