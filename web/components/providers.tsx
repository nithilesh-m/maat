"use client";
import { MotionConfig } from "framer-motion";
import { useEffect } from "react";
import { ThemeProvider } from "next-themes";
import { AccentProvider } from "@/components/accent";
import { AuthProvider } from "@/lib/auth";
import { QueryProvider } from "@/lib/query";

export function Providers({ children }: { children: React.ReactNode }) {
  // Lets E2E tests wait until React has attached its handlers before interacting.
  useEffect(() => {
    document.body.dataset.hydrated = "1";
  }, []);
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <MotionConfig reducedMotion="user">
        <AccentProvider>
          <AuthProvider>
            <QueryProvider>{children}</QueryProvider>
          </AuthProvider>
        </AccentProvider>
      </MotionConfig>
    </ThemeProvider>
  );
}
