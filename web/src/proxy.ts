import { NextResponse, type NextRequest } from "next/server";

export function proxy(request: NextRequest) {
  const development = process.env.NEXT_PUBLIC_APP_ENV !== "production";
  const publicPath =
    request.nextUrl.pathname.startsWith("/login") ||
    request.nextUrl.pathname.startsWith("/api/auth");
  if (!development && !publicPath && !request.cookies.has("ia_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("return_to", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
