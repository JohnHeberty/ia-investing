import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { clearSession, refreshSession } from "@/lib/oidc";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path[0] !== "api" || path[1] !== "v1")
    return NextResponse.json({ error: "Backend path is not allowed" }, { status: 404 });
  const base = process.env.IA_API_BASE_URL ?? "http://localhost:8000";
  const target = new URL(path.join("/"), `${base.replace(/\/$/, "")}/`);
  target.search = request.nextUrl.search;
  const jar = await cookies();
  let accessToken = jar.get("ia_access_token")?.value;
  if (!accessToken) return NextResponse.json({ error: "Authentication required" }, { status: 401 });

  const execute = (token: string) => {
    const headers = new Headers(request.headers);
    for (const name of ["cookie", "host", "content-length", "connection"]) headers.delete(name);
    headers.set("authorization", `Bearer ${token}`);
    headers.set("accept", "application/json");
    return fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      duplex: "half",
      cache: "no-store",
    } as RequestInit);
  };

  let response = await execute(accessToken);
  if (response.status === 401) {
    try {
      accessToken = (await refreshSession()) ?? undefined;
      if (accessToken) response = await execute(accessToken);
    } catch {
      await clearSession();
    }
  }
  const outgoingHeaders = new Headers(response.headers);
  outgoingHeaders.delete("transfer-encoding");

  const setCookies = response.headers.getSetCookie();
  const res = new NextResponse(response.body, { status: response.status, headers: outgoingHeaders });

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
