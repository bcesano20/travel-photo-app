"use client";

import { PropsWithChildren } from "react";
import { useRouter } from "next/navigation";

import { ROUTES } from "@/helpers/constants";
import { logout } from "@/helpers/auth";
import RequireAuth from "@/components/RequireAuth";

const AdminLayout = ({ children }: PropsWithChildren) => {
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push(ROUTES.LOGIN);
  };

  return (
    <RequireAuth>
      <div className="min-h-screen bg-neutral-50">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
            <span className="text-sm font-semibold text-neutral-900">Trip Gallery — Panel</span>
            <button
              onClick={handleLogout}
              className="text-sm text-neutral-500 hover:text-neutral-900"
            >
              Cerrar sesión
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </div>
    </RequireAuth>
  );
};

export default AdminLayout;
