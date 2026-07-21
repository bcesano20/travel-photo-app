"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ERROR_MESSAGES, REGEXP, ROUTES } from "@/helpers/constants";
import { AuthLoginInterface } from "@/helpers/interfaces";
import { login } from "@/helpers/auth";
import { Button, Input } from "@/components";

const DEFAULT_FORM_DATA: AuthLoginInterface = {
  email: "",
  password: "",
};

type LoginFormErrors = Partial<Record<keyof AuthLoginInterface, string>>;

export default function LoginPage() {
  const router = useRouter();

  const [loginData, setLoginData] = useState<AuthLoginInterface>(DEFAULT_FORM_DATA);
  const [formErrors, setFormErrors] = useState<LoginFormErrors>({});
  const [loading, setLoading] = useState<boolean>(false);

  const isValidForm = (): boolean => {
    const errors: LoginFormErrors = {};

    if (!loginData.email) {
      errors.email = ERROR_MESSAGES.FIELD_REQUIRED;
    } else if (!REGEXP.EMAIL_REGEX.test(loginData.email)) {
      errors.email = ERROR_MESSAGES.EMAIL_FORMAT_INVALID;
    }

    if (!loginData.password) {
      errors.password = ERROR_MESSAGES.FIELD_REQUIRED;
    }

    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValidForm()) return;

    setLoading(true);
    try {
      await login(loginData);
      router.push(ROUTES.ADMIN);
    } catch {
      setFormErrors({
        email: ERROR_MESSAGES.INCORRECT_CREDENTIALS_ES,
        password: ERROR_MESSAGES.INCORRECT_CREDENTIALS_ES,
      });
    } finally {
      setLoading(false);
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    setLoginData((prev) => ({ ...prev, [name]: value }));
    setFormErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-neutral-50 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm"
      >
        <h1 className="mb-6 text-xl font-semibold text-neutral-900">Iniciar sesión</h1>

        <div className="mb-4">
          <Input
            id="email"
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={loginData.email}
            onChange={handleChange}
            error={formErrors.email}
          />
        </div>

        <div className="mb-4">
          <Input
            id="password"
            name="password"
            label="Contraseña"
            type="password"
            autoComplete="current-password"
            required
            value={loginData.password}
            onChange={handleChange}
            error={formErrors.password}
          />
        </div>

        <Button type="submit" loading={loading} className="w-full">
          Ingresar
        </Button>
      </form>
    </main>
  );
}
