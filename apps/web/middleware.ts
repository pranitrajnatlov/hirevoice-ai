import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("hv_token")?.value;

  if (!token) {
    // Redirect to login if trying to access recruiter routes without a token
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/interviews/:path*",
    "/candidates/:path*",
    "/analytics/:path*",
  ],
};
