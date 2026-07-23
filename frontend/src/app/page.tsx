"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { isAuthenticated } from "@/helpers/auth";
import { ROUTES } from "@/helpers/constants";

const Home = () => {
  const router = useRouter();

  useEffect(() => {
    router.replace(isAuthenticated() ? ROUTES.ADMIN : ROUTES.LOGIN);
  }, [router]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50">
      <p className="text-sm text-neutral-500">Cargando...</p>
    </main>
  );
};

export default Home;
