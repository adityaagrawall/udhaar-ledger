"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { MotionConfig } from "framer-motion";
import { useAuth } from "@clerk/nextjs";
import { apiFetch, registerAuth } from "@/lib/api";

export interface Me {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "manager" | "viewer";
  is_demo: boolean;
  org_name: string | null;
}

interface MeState {
  me: Me | null;
  loading: boolean;
  /** Admins and managers can change records; viewers (including the demo) cannot. */
  canEdit: boolean;
}

const MeContext = createContext<MeState>({ me: null, loading: true, canEdit: false });
export const useMe = () => useContext(MeContext);

function AuthBridge({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const [state, setState] = useState<MeState>({ me: null, loading: true, canEdit: false });

  useEffect(() => {
    if (!isLoaded) return;
    registerAuth(() => getToken(), () => signOut({ redirectUrl: "/login" }));
    if (!isSignedIn) {
      setState({ me: null, loading: false, canEdit: false });
      return;
    }
    apiFetch<Me>("/auth/me")
      .then((me) => setState({ me, loading: false, canEdit: me.role !== "viewer" }))
      .catch(() => setState({ me: null, loading: false, canEdit: false }));
  }, [isLoaded, isSignedIn, getToken, signOut]);

  return <MeContext.Provider value={state}>{children}</MeContext.Provider>;
}

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <AuthBridge>{children}</AuthBridge>
    </MotionConfig>
  );
}
