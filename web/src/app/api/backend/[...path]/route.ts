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
  outgoingHeaders.delete("set-cookie");
  outgoingHeaders.delete("transfer-encoding");
  return new NextResponse(response.body, { status: response.status, headers: outgoingHeaders });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
