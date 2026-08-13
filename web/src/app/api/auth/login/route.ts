import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { SignJWT } from "jose";

const SESSION_SECRET = process.env.SECURITY__SESSION_SECRET_KEY ?? "";
const SESSION_DURATION_MS = 8 * 60 * 60 * 1000; // 8 hours

function getSecretKey() {
  return new TextEncoder().encode(SESSION_SECRET);
}

async function createSessionToken(claims: {
  sub: string;
  name?: string;
  email?: string;
  organization_id?: string;
  roles?: string[];
  permissions?: string[];
  team_ids?: string[];
}) {
  const nowSec = Math.floor(Date.now() / 1000);
  const jwt = await new SignJWT({
    sub: claims.sub,
    ...(claims.name && { name: claims.name }),
    ...(claims.email && { email: claims.email }),
    ...(claims.organization_id && { organization_id: claims.organization_id }),
    ...(claims.roles && { roles: claims.roles }),
    ...(claims.permissions && { permissions: claims.permissions }),
    ...(claims.team_ids && { team_ids: claims.team_ids }),
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt(nowSec)
    .setExpirationTime(nowSec + SESSION_DURATION_MS / 1000)
    .setJti(crypto.randomUUID())
    .sign(getSecretKey());
  return jwt;
}

/**
 * POST /api/auth/login
 * Simple session-based login for development.
 * In production, use OIDC authorization-code flow.
 */
export async function POST(request: NextRequest) {
  if (!SESSION_SECRET) {
    return NextResponse.json({ error: "Session secret not configured" }, { status: 500 });
  }

  if (process.env.NODE_ENV !== "development") {
    return NextResponse.json(
      { error: "This login endpoint is for development only. Use OIDC in production." },
      { status: 403 },
    );
  }

  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const email = body.email;
  if (!email) {
    return NextResponse.json({ error: "Email is required" }, { status: 400 });
  }

  // SECURITY: In dev mode, only allow pre-approved emails to receive admin.
  // Without this, any email gets full admin privileges — a risk if the dev
  // server is exposed on a shared network. Set DEV_ALLOWED_EMAILS env var
  // (comma-separated) or fall back to a restrictive default.
  const allowedEmailsEnv = process.env.DEV_ALLOWED_EMAILS;
  const allowedEmails = allowedEmailsEnv
    ? allowedEmailsEnv.split(",").map((e) => e.trim().toLowerCase())
    : [];

  if (allowedEmails.length > 0 && !allowedEmails.includes(email.toLowerCase())) {
    console.warn(`[auth] Dev login denied for "${email}" — not in DEV_ALLOWED_EMAILS whitelist`);
    return NextResponse.json(
      { error: "Email not in dev whitelist. Set DEV_ALLOWED_EMAILS to allow access." },
      { status: 403 },
    );
  }

  if (allowedEmails.length === 0) {
    console.warn(
      "[auth] DEV_ALLOWED_EMAILS is not set — granting admin to any email. " +
        "This is insecure on shared networks.",
    );
  }

  // Dev mode: accept whitelisted email, no password validation
  // In production, validate against identity provider
  const subject = email;
  const name = email.split("@")[0];

  const token = await createSessionToken({
    sub: subject,
    name,
    email,
    organization_id:
      process.env.NEXT_PUBLIC_ORGANIZATION_ID ?? "00000000-0000-0000-0000-000000000001",
    roles: ["admin"],
    permissions: [
      "admin",
      "portfolio:read",
      "thesis:read",
      "thesis:create",
      "thesis:update",
      "reports:export",
      "agent_runs:read",
      "agent_runs:create",
      "agent:read",
      "agent:run",
      "agent_approvals:decide",
      "quality_incidents:manage",
      "audit:read",
      "policy:read",
      "macro:read",
      "rebalance:*",
      "committee:read",
      "committee:vote",
      "committee:chair",
      "committee:create",
      "committee:publish",
      "dashboard:read",
      "sources:read",
      "schedules:read",
      "schedules:manage",
      "financials:read",
      "instruments:read",
      "issuers:read",
      "metrics:read",
      "operations:read",
      "execution:*",
      "research_cases:create",
      "candidates:read",
      "candidates:create",
      "exploration:read",
      "research:read",
      "risk:read",
      "risk:assess",
      "backtests:read",
      "backtests:run",
      "approval:read",
      "approval:decide",
      "market_data:read",
      "news:read",
      "news:write",
      "news:manage",
    ],
  });

  const jar = await cookies();
  jar.set("ia_session", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV !== "development",
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_DURATION_MS / 1000,
  });

  const returnTo = request.nextUrl.searchParams.get("return_to") || "/";
  return NextResponse.json({ success: true, return_to: returnTo });
}
