import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("hv_token")?.value;
  const path = request.nextUrl.pathname;

  const isProtectedRoute = 
    path.startsWith("/dashboard") ||
    path.startsWith("/interviews") ||
    path.startsWith("/candidates") ||
    path.startsWith("/analytics");

  const isAuthRoute = path === "/" || path === "/login" || path === "/register";

  if (isProtectedRoute && !token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (isAuthRoute && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt|interview/.*).*)',
  ],
};
