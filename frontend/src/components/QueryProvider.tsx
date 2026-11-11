"use client";

import { PropsWithChildren, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { QUERY_GC_TIME_MS, QUERY_STALE_TIME_MS } from "@/helpers/constants";

export const QueryProvider = ({ children }: PropsWithChildren) => {
  // useState (not a module-level constant) so each browser session gets its
  // own client and the cache is never shared between server-rendered requests.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: QUERY_STALE_TIME_MS,
            gcTime: QUERY_GC_TIME_MS,
            retry: 1,
          },
        },
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};
