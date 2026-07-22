import { NextResponse, type NextRequest } from "next/server";

const publicPaths = ["/login", "/api/auth"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic = publicPaths.some((p) => pathname === p || pathname.startsWith(p));
  const isStatic =
    pathname.startsWith("/_next") || pathname.startsWith("/favicon") || pathname === "/";

  if (isPublic || isStatic) {
    return NextResponse.next();
  }

  if (!request.cookies.has("ia_session")) {
    const login = new URL("/login", request.url);
    login.searchParams.set("return_to", pathname);
    return NextResponse.redirect(login);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
