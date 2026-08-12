"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const bffBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/backend";

export type UserInfo = {
  subject: string;
  name: string | null;
  email: string | null;
  organization_id: string | null;
  roles: string[];
  team_ids: string[];
  permissions: string[];
};

type AuthContextValue = {
  user: UserInfo | null;
  loading: boolean;
  error: string | null;
  login: (email: string, returnTo?: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  error: null,
  login: async () => {},
  logout: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

async function fetchUser(): Promise<UserInfo | null> {
  try {
    const response = await fetch(`${bffBase}/api/v1/auth/me`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      if (response.status === 401) return null;
      throw new Error(`Auth check failed: ${response.status}`);
    }
    return response.json() as Promise<UserInfo>;
  } catch (err) {
    console.error("[auth] fetchUser failed:", err);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchUser()
      .then((u) => {
        if (!cancelled) {
          setUser(u);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Authentication check failed");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, returnTo?: string) => {
      const params = new URLSearchParams();
      if (returnTo) params.set("return_to", returnTo);
      const qs = params.toString();

      const response = await fetch(`/api/auth/login${qs ? `?${qs}` : ""}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error((data as { error?: string }).error || "Login failed");
      }

      const result = await response.json() as { return_to?: string };
      setUser(null);
      setLoading(true);
      window.location.href = result.return_to || returnTo || "/";
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await fetch("/api/auth/logout", {
        credentials: "include",
      });
    } catch {
      // proceed even if server request fails
    }
    setUser(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
