import { NextResponse } from "next/server";

import { clearSession, refreshSession } from "@/lib/oidc";

export async function POST() {
  try {
    const accessToken = await refreshSession();
    if (!accessToken) return NextResponse.json({ error: "No refresh session" }, { status: 401 });
    return NextResponse.json({ refreshed: true });
  } catch {
    await clearSession();
    return NextResponse.json({ error: "Session refresh failed" }, { status: 401 });
  }
}
