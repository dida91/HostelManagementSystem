import { type NextRequest, NextResponse } from "next/server";

/**
 * Send signed-out visitors to /login before any page renders (no flash of an
 * empty app). This is a convenience, not the security boundary: FastAPI
 * authorises every request. A present cookie may still be expired; the client
 * then renews it or returns to /login.
 */
export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession =
    request.cookies.has("refresh_token") || request.cookies.has("access_token");
  if (hasSession || pathname === "/login") return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Everything except the BFF, Next internals and static files.
  matcher: ["/((?!api/|_next/|favicon\\.ico|.*\\.[a-zA-Z0-9]+$).*)"],
};
