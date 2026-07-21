"use client";

import { useEffect, useSyncExternalStore } from "react";
import { useRouter } from "next/navigation";

import { ROUTES } from "@/helpers/constants";
import { isAuthenticated } from "@/helpers/auth";

function subscribe() {
  // Auth changes (login/logout) happen via full navigations in this app,
  // not in-place storage events within the same tab, so there's nothing to
  // subscribe to — this store only needs to report the current snapshot.
  return () => {};
}

// getServerSnapshot always returns false, so server-rendered and first-hydration
// output match (localStorage doesn't exist on the server) — avoids a hydration
// mismatch without needing an effect + extra render pass to "reveal" content.
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const authenticated = useSyncExternalStore(subscribe, isAuthenticated, () => false);

  useEffect(() => {
    if (!authenticated) {
      router.replace(ROUTES.LOGIN);
    }
  }, [authenticated, router]);

  // Render nothing until we've confirmed there's a token, so protected
  // content never flashes on screen for a logged-out visitor.
  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}
