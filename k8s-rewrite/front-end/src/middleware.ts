import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSessionFromHeaders } from "@/lib/auth";

// Routes that don't require authentication
const PUBLIC_PATHS = ["/welcome", "/auth/login", "/auth/register"];
const PUBLIC_PREFIXES = ["/api/auth/", "/_next/", "/favicon.ico", "/api/cluster/info"];

function isPublic(pathname: string): boolean {
  if (PUBLIC_PATHS.includes(pathname)) return true;
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public routes through
  if (isPublic(pathname)) return NextResponse.next();

  // Check authentication
  const session = await getSessionFromHeaders(
    request.headers.get("cookie")
  );

  if (session) {
    // Authenticated — allow through
    return NextResponse.next();
  }

  // API routes — return 401 JSON
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Page routes — redirect to welcome (which will route to login if needed)
  const welcomeUrl = new URL("/welcome", request.url);
  return NextResponse.redirect(welcomeUrl);
}

export const config = {
  matcher: [
    /*
     * Match all paths except static files
     */
    "/((?!_next/static|_next/image).*)",
  ],
};
