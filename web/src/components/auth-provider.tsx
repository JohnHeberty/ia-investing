"use client";

import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const bffBase = process.env.NEXT_PUBLIC_IA_BFF_BASE_URL ?? "/api/backend";

export type UserInfo = {
  subject: string;
  name: string | null;
  email: string | null;
  organization_id: string | null;
  roles: string[];
  team_ids: string[];
};

type AuthContextValue = {
  user: UserInfo | null;
  loading: boolean;
  error: string | null;
  login: (returnTo?: string) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  error: null,
  login: () => {},
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
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
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
  }, [pathname]);

  const login = useCallback(
    (returnTo?: string) => {
      const params = new URLSearchParams();
      if (returnTo) params.set("return_to", returnTo);
      const qs = params.toString();
      window.location.href = `${bffBase}/api/v1/auth/authorize${qs ? `?${qs}` : ""}`;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await fetch(`${bffBase}/api/v1/auth/logout`, {
        method: "POST",
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
