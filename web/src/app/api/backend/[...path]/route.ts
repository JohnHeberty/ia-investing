import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path[0] !== "api" || path[1] !== "v1")
    return NextResponse.json({ error: "Backend path is not allowed" }, { status: 404 });
  const base = process.env.IA_API_BASE_URL ?? "http://localhost:8000";
  const target = new URL(path.join("/"), `${base.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;
  const jar = await cookies();

  // Check for any session cookie — backend validates which ones it needs
  const hasSessionCookie = jar.get("ia_session")?.value != null;

  // Auth routes are public — allow without any auth
  const isAuthRoute = path[2] === "auth";

  if (!hasSessionCookie && !isAuthRoute) {
    return NextResponse.json(
      { error: "Authentication required (no ia_session cookie in proxy)" },
      { status: 401 },
    );
  }

  const execute = () => {
    const headers = new Headers(request.headers);
    for (const name of ["host", "content-length", "connection"]) headers.delete(name);

    // Forward all cookies to backend — the backend validates each one it needs
    // (ia_session for auth, ia_csrf_token for CSRF checks, etc.)
    const allCookies = jar.getAll();
    if (allCookies.length > 0) {
      const cookieHeader = allCookies.map((c) => `${c.name}=${c.value}`).join("; ");
      headers.set("cookie", cookieHeader);
    }

    headers.set("accept", "application/json");
    return fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      duplex: "half",
      cache: "no-store",
    } as RequestInit);
  };

  let response: Response;
  try {
    response = await execute();
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Backend unreachable";
    return NextResponse.json({ error: "Backend fetch failed", detail }, { status: 502 });
  }

  const outgoingHeaders = new Headers(response.headers);
  outgoingHeaders.delete("transfer-encoding");

  const setCookies = response.headers.getSetCookie();
  const res = new NextResponse(response.body, {
    status: response.status,
    headers: outgoingHeaders,
  });

  // Forward CSRF token from backend to client
  for (const raw of setCookies) {
    const name = raw.split("=")[0].trim();
    if (name === "ia_csrf_token") {
      const value = raw.split(";")[0].split("=").slice(1).join("=");
      res.cookies.set("ia_csrf_token", value, {
        path: "/",
        httpOnly: false,
        secure: process.env.NODE_ENV === "production",
        sameSite: "strict",
        maxAge: 28_800,
      });
    }
  }

  return res;
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
