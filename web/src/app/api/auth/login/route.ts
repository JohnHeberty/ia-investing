import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import {
  oidcConfig,
  pkceChallenge,
  randomUrlSafe,
  safeReturnTo,
  transientCookie,
} from "@/lib/oidc";

export async function GET(request: NextRequest) {
  try {
    const config = oidcConfig();
    const state = randomUrlSafe();
    const nonce = randomUrlSafe();
    const verifier = randomUrlSafe(48);
    const jar = await cookies();
    jar.set("ia_oidc_state", state, transientCookie);
    jar.set("ia_oidc_nonce", nonce, transientCookie);
    jar.set("ia_oidc_verifier", verifier, transientCookie);
    jar.set(
      "ia_return_to",
      safeReturnTo(request.nextUrl.searchParams.get("return_to")),
      transientCookie,
    );
    const authorization = new URL(config.authorizationUrl);
    authorization.search = new URLSearchParams({
      response_type: "code",
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      scope: config.scope,
      state,
      nonce,
      code_challenge: pkceChallenge(verifier),
      code_challenge_method: "S256",
    }).toString();
    return NextResponse.redirect(authorization);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "OIDC login failed" },
      { status: 503 },
    );
  }
}
