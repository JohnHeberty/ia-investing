"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";

const bffBase = process.env.NEXT_PUBLIC_IA_BFF_BASE_URL ?? "/api/backend";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const returnTo = searchParams.get("return_to") || "/";

  useEffect(() => {
    if (!loading && user) {
      router.replace(returnTo);
    }
  }, [loading, user, router, returnTo]);

  if (loading) {
    return <div className="subtitle" style={{ textAlign: "center" }}>Verificando sessão…</div>;
  }

  if (user) {
    return null;
  }

  async function handlePasswordLogin(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLoginError(null);
    try {
      const response = await fetch(`${bffBase}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error((data as { detail?: string }).detail || "Login failed");
      }
      window.location.href = returnTo;
    } catch (err: unknown) {
      setLoginError(err instanceof Error ? err.message : "Erro ao autenticar");
    } finally {
      setSubmitting(false);
    }
  }

  function handleSSO() {
    const params = new URLSearchParams();
    if (returnTo !== "/") params.set("return_to", returnTo);
    const qs = params.toString();
    window.location.href = `${bffBase}/api/v1/auth/authorize${qs ? `?${qs}` : ""}`;
  }

  return (
    <>
      <h1>Entrar no IA Investing OS</h1>
      <p className="subtitle">
        Use seu provedor OIDC institucional ou faça login com email e senha.
      </p>

      {loginError && (
        <div role="alert" className="alert-error">
          {loginError}
        </div>
      )}

      <form onSubmit={handlePasswordLogin} className="login-form">
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
          />
        </div>
        <div className="field">
          <label htmlFor="password">Senha</label>
          <input
            id="password"
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={submitting}
            placeholder="••••••••"
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={submitting}>
          {submitting ? "Autenticando…" : "Entrar"}
        </button>
      </form>

      <div className="divider">
        <span>ou</span>
      </div>

      <button className="btn btn-outline" onClick={handleSSO} type="button">
        Continuar com SSO
      </button>

      <p className="footnote">
        Voltar para o <Link href="/">início</Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <div className="card card-pad" style={{ maxWidth: 430, margin: "12vh auto" }}>
      <div className="eyebrow">Identidade institucional</div>
      <Suspense fallback={<div className="subtitle" style={{ textAlign: "center" }}>Carregando…</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
