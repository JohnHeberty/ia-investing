import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { decodeJwtPayload } from "@/lib/oidc";

export async function GET() {
  const token = (await cookies()).get("ia_id_token")?.value;
  if (!token) return NextResponse.json({ authenticated: false }, { status: 401 });
  try {
    const claims = decodeJwtPayload(token);
    return NextResponse.json({
      authenticated: true,
      subject: claims.sub,
      name: claims.name,
      organizationId: claims.organization_id,
      teamIds: claims.team_ids ?? [],
      timezone: claims.zoneinfo ?? "America/Sao_Paulo",
    });
  } catch {
    return NextResponse.json({ authenticated: false }, { status: 401 });
  }
}
