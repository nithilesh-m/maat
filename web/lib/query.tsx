"use client";
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "./api/client";
import { useAuth } from "./auth";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const { logout } = useAuth();
  // Review Focus #1: a 401 anywhere ends the session once, with a message, and never loops.
  const onError = (e: unknown) => {
    if (e instanceof ApiError && e.status === 401) logout("expired");
  };
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError }),
        mutationCache: new MutationCache({ onError }),
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            retry: (n, e) =>
              !(e instanceof ApiError && [401, 403, 404, 409, 422].includes(e.status)) && n < 2,
          },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
