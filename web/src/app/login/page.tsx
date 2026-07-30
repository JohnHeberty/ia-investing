"use client";

import type { Route } from "next";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const rawReturnTo = searchParams.get("return_to") || "/";
  const returnTo = rawReturnTo.startsWith("/") && !rawReturnTo.startsWith("//") ? rawReturnTo : "/";

  useEffect(() => {
    if (!loading && user) {
      router.replace(returnTo as Route);
    }
  }, [loading, user, router, returnTo]);

  if (loading) {
    return <div className="subtitle" style={{ textAlign: "center" }}>Verificando sessão…</div>;
  }

  if (user) {
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLoginError(null);
    try {
      await login(email, returnTo);
    } catch (err: unknown) {
      setLoginError(err instanceof Error ? err.message : "Erro ao autenticar");
      setSubmitting(false);
    }
  }

  return (
    <>
      <h1>Entrar no IA Investing OS</h1>
      <p className="subtitle">
        Digite seu email para autenticar.
      </p>

      {loginError && (
        <div role="alert" className="alert-error">
          {loginError}
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            placeholder="seu@email.com"
            autoFocus
          />
        </div>
        <button
          className="btn btn-primary"
          type="submit"
          disabled={submitting || !email}
          style={{ width: "100%", marginTop: 8 }}
        >
          {submitting ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </>
  );
}

export default function LoginPage() {
  return (
    <div className="card card-pad" style={{ maxWidth: 430, width: "100%", margin: "0 16px" }}>
      <div className="eyebrow">Identidade institucional</div>
      <Suspense fallback={<div className="subtitle" style={{ textAlign: "center" }}>Carregando…</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
