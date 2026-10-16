import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSessionFromHeaders } from "@/lib/auth";

// Routes that don't require authentication
const PUBLIC_PATHS = ["/welcome", "/auth/login", "/auth/register", "/api/vars/lookup", "/api/kv/automation", "/api/health/live", "/api/health/ready", "/api/cluster/info", "/favicon.ico"];
const PUBLIC_PREFIXES = ["/api/auth/", "/_next/"];
const AUTH_FAILURE_HEADERS = { "Cache-Control": "no-store, private", Pragma: "no-cache" };

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public routes through
  if (isPublic(pathname)) return NextResponse.next();

  // Check authentication
  let session;
  try { session = await getSessionFromHeaders(request.headers.get("cookie")); }
  catch { return NextResponse.json({ error: "Authentication service unavailable" }, { status: 503, headers: AUTH_FAILURE_HEADERS }); }

  if (session) {
    // Authenticated — allow through
    return NextResponse.next();
  }

  // API routes — return 401 JSON
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401, headers: AUTH_FAILURE_HEADERS });
  }

  // Page routes — redirect to welcome (which will route to login if needed)
  const welcomeUrl = new URL("/welcome", request.url);
  return NextResponse.redirect(welcomeUrl);
}

export const config = {
  runtime: "nodejs",
  matcher: [
    /*
     * Match all paths except static files
     */
    "/((?!_next/static|_next/image).*)",
  ],
};
