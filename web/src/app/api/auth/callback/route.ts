import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import {
  clearSession,
  decodeJwtPayload,
  exchangeCode,
  safeReturnTo,
  storeTokenSet,
} from "@/lib/oidc";

export async function GET(request: NextRequest) {
  const jar = await cookies();
  const code = request.nextUrl.searchParams.get("code");
  const state = request.nextUrl.searchParams.get("state");
  const expectedState = jar.get("ia_oidc_state")?.value;
  const verifier = jar.get("ia_oidc_verifier")?.value;
  const expectedNonce = jar.get("ia_oidc_nonce")?.value;
  const returnTo = safeReturnTo(jar.get("ia_return_to")?.value ?? null);
  if (!code || !state || !expectedState || state !== expectedState || !verifier || !expectedNonce) {
    await clearSession();
    return NextResponse.json({ error: "Invalid or expired OIDC callback state" }, { status: 400 });
  }
  try {
    const tokens = await exchangeCode(code, verifier);
    if (!tokens.id_token || decodeJwtPayload(tokens.id_token).nonce !== expectedNonce)
      throw new Error("OIDC nonce validation failed");
    await storeTokenSet(tokens);
    jar.delete("ia_oidc_state");
    jar.delete("ia_oidc_nonce");
    jar.delete("ia_oidc_verifier");
    jar.delete("ia_return_to");
    return NextResponse.redirect(new URL(returnTo, request.url));
  } catch (error) {
    await clearSession();
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "OIDC callback failed" },
      { status: 401 },
    );
  }
}
