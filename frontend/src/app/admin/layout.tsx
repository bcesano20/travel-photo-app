"use client";

import { PropsWithChildren } from "react";
import { useRouter } from "next/navigation";

import { ROUTES } from "@/helpers/constants";
import { logout } from "@/helpers/auth";
import RequireAuth from "@/components/RequireAuth";
import { Button } from "@/components";

const AdminLayout = ({ children }: PropsWithChildren) => {
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push(ROUTES.LOGIN);
  };

  return (
    <RequireAuth>
      <div className="bg-foreground min-h-screen">
        <header className="border-b border-neutral-200 bg-sky-100">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
            <span className="text-foreground text-[18px] font-semibold md:text-[30px]">
              Galeria de Viajes — Panel
            </span>
            <Button
              onClick={handleLogout}
              className="rounded-[30px] bg-red-800 text-sm text-white transition-transform hover:scale-110"
            >
              Cerrar sesión
            </Button>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </div>
    </RequireAuth>
  );
};

export default AdminLayout;
