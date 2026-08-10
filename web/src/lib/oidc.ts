// Server-only module — these functions use cookies() from next/headers
// and must only be called from Server Actions or Route Handlers.
import { cookies } from "next/headers";
import { createRemoteJWKSet, jwtVerify, type JWTPayload } from "jose";

export interface OidcConfig {
  clientId: string;
  clientSecret: string;
  authorizationUrl: string;
  tokenUrl: string;
  redirectUri: string;
  scope: string;
  endSessionUrl?: string;
}

export interface TokenSet {
  access_token: string;
  id_token: string;
  refresh_token?: string;
  expires_in?: number;
}

export interface JwtClaims extends JWTPayload {
  sub: string;
  name: string;
  email?: string;
  nonce?: string;
  organization_id?: string;
  team_ids?: string[];
  zoneinfo?: string;
}

let _jwks: ReturnType<typeof createRemoteJWKSet> | null = null;

function getJwks() {
  if (!_jwks) {
    const jwksUrl = process.env.OIDC_JWKS_URL;
    if (!jwksUrl) throw new Error("OIDC_JWKS_URL is not configured");
    _jwks = createRemoteJWKSet(new URL(jwksUrl));
  }
  return _jwks;
}

/**
 * Verify a JWT's signature, expiration, issuer, and audience using the OIDC provider's JWKS.
 * Returns the validated claims. Throws on any verification failure.
 */
export async function verifyJwt(token: string): Promise<JwtClaims> {
  const issuer = process.env.OIDC_ISSUER;
  const audience = process.env.OIDC_CLIENT_ID;
  const { payload } = await jwtVerify(token, getJwks(), {
    issuer: issuer ?? undefined,
    audience: audience ?? undefined,
  });
  return payload as JwtClaims;
}

export function oidcConfig(): OidcConfig {
  return {
    clientId: process.env.OIDC_CLIENT_ID ?? "",
    clientSecret: process.env.OIDC_CLIENT_SECRET ?? "",
    authorizationUrl: process.env.OIDC_AUTHORIZATION_URL ?? "",
    tokenUrl: process.env.OIDC_TOKEN_URL ?? "",
    redirectUri: process.env.OIDC_REDIRECT_URI ?? "",
    scope: process.env.OIDC_SCOPE ?? "openid profile email",
    endSessionUrl: process.env.OIDC_END_SESSION_URL,
  };
}

function base64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

export async function pkceChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  return crypto.subtle.digest("SHA-256", data).then((hash) => base64Url(new Uint8Array(hash)));
}

export function randomUrlSafe(length = 32): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

export const transientCookie = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 300,
};

export async function exchangeCode(code: string, codeVerifier: string): Promise<TokenSet> {
  const config = oidcConfig();
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    code,
    code_verifier: codeVerifier,
    redirect_uri: config.redirectUri,
    client_id: config.clientId,
    client_secret: config.clientSecret,
  });
  const response = await fetch(config.tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "Unknown error");
    throw new Error(`Token exchange failed: ${response.status} ${text}`);
  }
  return response.json() as Promise<TokenSet>;
}

const sessionCookieOpts = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
};

export async function storeTokenSet(tokens: TokenSet): Promise<void> {
  const jar = await cookies();
  jar.set("ia_access_token", tokens.access_token, {
    ...sessionCookieOpts,
    maxAge: tokens.expires_in ?? 900,
  });
  jar.set("ia_id_token", tokens.id_token, { ...sessionCookieOpts, maxAge: 3600 });
  if (tokens.refresh_token) {
    jar.set("ia_refresh_token", tokens.refresh_token, {
      ...sessionCookieOpts,
      maxAge: 86400 * 30,
    });
  }
}

export async function clearSession(): Promise<void> {
  const jar = await cookies();
  jar.delete("ia_access_token");
  jar.delete("ia_id_token");
  jar.delete("ia_refresh_token");
  jar.delete("ia_oidc_state");
  jar.delete("ia_oidc_nonce");
  jar.delete("ia_oidc_verifier");
  jar.delete("ia_return_to");
}

export async function refreshSession(): Promise<string | null> {
  const config = oidcConfig();
  const jar = await cookies();
  const refreshToken = jar.get("ia_refresh_token")?.value;
  if (!refreshToken) return null;
  const body = new URLSearchParams({
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    client_id: config.clientId,
    client_secret: config.clientSecret,
  });
  const response = await fetch(config.tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    signal: AbortSignal.timeout(30_000),
  });
  if (!response.ok) {
    await clearSession();
    return null;
  }
  const tokens = (await response.json()) as TokenSet;
  await storeTokenSet(tokens);
  return tokens.access_token;
}

export function safeReturnTo(url: string | null): string {
  if (!url) return "/";
  try {
    const parsed = new URL(url, "http://localhost");
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "/";
    const allowedHosts = new Set(
      [
        "localhost",
        "127.0.0.1",
        process.env.NEXT_PUBLIC_APP_HOST,
      ].filter(Boolean),
    );
    if (parsed.hostname && !allowedHosts.has(parsed.hostname)) {
      return "/";
    }
    return parsed.pathname + parsed.search;
  } catch {
    return "/";
  }
}
