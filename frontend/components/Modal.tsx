"use client";

import { createContext, useContext, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { useDialogBehavior } from "@/components/useDialogBehavior";

const TitleContext = createContext<string | undefined>(undefined);

/** Heading that names the surrounding dialog (aria-labelledby is wired up by <Modal>). */
export function ModalTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  const id = useContext(TitleContext);
  return (
    <h2 id={id} className={className}>
      {children}
    </h2>
  );
}

/**
 * Accessible modal dialog.
 *
 * - role="dialog" + aria-modal, named by <ModalTitle>
 * - focus moves in on open (to [data-autofocus] or the first control), is trapped, and returns to the trigger on close
 * - Escape closes; the page behind is inert and does not scroll
 * - rendered in a portal so making the rest of the page inert cannot affect the dialog
 */
export default function Modal({
  onClose,
  children,
  className = "",
  backdropClassName = "",
}: {
  onClose: () => void;
  children: React.ReactNode;
  /** Classes for the dialog panel. */
  className?: string;
  /** Extra classes for the backdrop (e.g. overflow-y-auto). */
  backdropClassName?: string;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  useDialogBehavior(panel, onClose);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div>
      <motion.div
        className={`fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4 sm:p-6 ${backdropClassName}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.15 }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
      >
        <TitleContext.Provider value={titleId}>
          <motion.div
            ref={panel}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            tabIndex={-1}
            className={`focus:outline-none ${className}`}
            initial={{ opacity: 0, y: 18, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          >
            {children}
          </motion.div>
        </TitleContext.Provider>
      </motion.div>
    </div>,
    document.body
  );
}
