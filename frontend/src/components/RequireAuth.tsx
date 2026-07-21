"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ROUTES } from "@/helpers/constants";
import { isAuthenticated } from "@/helpers/auth";

export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  const [checked, setChecked] = useState<boolean>(false);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace(ROUTES.LOGIN);
      return;
    }
    setChecked(true);
  }, [router]);

  // Render nothing until we've confirmed there's a token, so protected
  // content never flashes on screen for a logged-out visitor.
  if (!checked) {
    return null;
  }

  return <>{children}</>;
}
