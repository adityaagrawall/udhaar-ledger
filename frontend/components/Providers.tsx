"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
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

type Politeness = "polite" | "assertive";
const AnnounceContext = createContext<(message: string, politeness?: Politeness) => void>(() => {});
/** Announce a status change to screen readers (e.g. "Loaded 12 accounts"). Use "assertive" only for errors. */
export const useAnnounce = () => useContext(AnnounceContext);

function Announcer({ children }: { children: React.ReactNode }) {
  const [polite, setPolite] = useState("");
  const [assertive, setAssertive] = useState("");
  const flip = useRef(false);
  const announce = useCallback((message: string, politeness: Politeness = "polite") => {
    // A trailing non-breaking space makes a repeated message count as a change, so it is announced again.
    flip.current = !flip.current;
    const text = flip.current ? message : `${message}\u00a0`;
    if (politeness === "assertive") setAssertive(text);
    else setPolite(text);
  }, []);
  return (
    <AnnounceContext.Provider value={announce}>
      {children}
      <div data-live-region role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {polite}
      </div>
      <div data-live-region role="alert" aria-live="assertive" aria-atomic="true" className="sr-only">
        {assertive}
      </div>
    </AnnounceContext.Provider>
  );
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
      <Announcer>
        <AuthBridge>{children}</AuthBridge>
      </Announcer>
    </MotionConfig>
  );
}
