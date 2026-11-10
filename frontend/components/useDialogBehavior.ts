"use client";

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]):not([type=hidden]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Keyboard and focus behaviour shared by modal dialogs and the mobile navigation drawer.
 *
 * - focus moves into the panel on mount (to [data-autofocus] or the first control)
 * - Tab and Shift+Tab are trapped inside the panel; Escape calls onClose
 * - the rest of the page is made inert and stops scrolling while the panel is mounted
 * - focus returns to whatever had it before when the panel unmounts
 */
export function useDialogBehavior(panel: RefObject<HTMLElement>, onClose: () => void) {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const node = panel.current;
    if (!node) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;

    const inerted: HTMLElement[] = [];
    for (const el of Array.from(document.body.children) as HTMLElement[]) {
      if (el.contains(node) || el.tagName === "SCRIPT" || el.tagName === "NEXT-ROUTE-ANNOUNCER" || el.hasAttribute("data-live-region")) continue;
      if (!el.hasAttribute("inert")) {
        el.setAttribute("inert", "");
        inerted.push(el);
      }
    }
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const frame = requestAnimationFrame(() => {
      const target = node.querySelector<HTMLElement>("[data-autofocus]") ?? node.querySelector<HTMLElement>(FOCUSABLE) ?? node;
      target.focus();
      // A disabled or hidden target cannot take focus; keep it inside the dialog rather than on the inert page.
      if (!node.contains(document.activeElement)) node.focus();
    });

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null);
      if (items.length === 0) {
        e.preventDefault();
        node.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || active === node)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);

    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKeyDown);
      inerted.forEach((el) => el.removeAttribute("inert"));
      document.body.style.overflow = prevOverflow;
      if (previouslyFocused && document.contains(previouslyFocused)) previouslyFocused.focus();
    };
  }, [panel]);
}
