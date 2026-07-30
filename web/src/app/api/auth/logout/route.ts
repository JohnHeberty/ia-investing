import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function GET() {
  const jar = await cookies();
  jar.delete("ia_session");
  jar.delete("ia_csrf_token");
  jar.delete("ia_access_token");
  jar.delete("ia_id_token");
  jar.delete("ia_refresh_token");
  return NextResponse.redirect(new URL("/login", "http://localhost:3000"));
}
