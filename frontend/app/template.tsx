"use client";

import { motion } from "framer-motion";

/** Re-mounts on every navigation, giving each page a soft entrance. */
export default function Template({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      className="flex-1 flex flex-col min-w-0"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}
