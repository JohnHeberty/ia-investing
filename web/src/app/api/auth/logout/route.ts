import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const jar = await cookies();
  jar.delete("ia_session");
  jar.delete("ia_csrf_token");
  jar.delete("ia_access_token");
  jar.delete("ia_id_token");
  jar.delete("ia_refresh_token");

  const origin = request.nextUrl.origin;
  return NextResponse.redirect(new URL("/login", origin));
}

export async function GET(request: NextRequest) {
  return POST(request);
}
