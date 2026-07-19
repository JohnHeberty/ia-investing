import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

import { clearSession, oidcConfig } from "@/lib/oidc";

export async function GET(request: NextRequest) {
  const jar = await cookies();
  const idToken = jar.get("ia_id_token")?.value;
  let destination = new URL("/login", request.url);
  try {
    const config = oidcConfig();
    if (config.endSessionUrl) {
      destination = new URL(config.endSessionUrl);
      destination.searchParams.set(
        "post_logout_redirect_uri",
        new URL("/login", request.url).toString(),
      );
      if (idToken) destination.searchParams.set("id_token_hint", idToken);
    }
  } finally {
    await clearSession();
  }
  return NextResponse.redirect(destination);
}
