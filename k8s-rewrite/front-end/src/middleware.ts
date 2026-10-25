import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSessionFromHeaders } from "@/lib/auth";
import { GET as getPodMetadata } from "@/app/api/cluster/pods/route";

// Routes that don't require authentication
const PUBLIC_PATHS = [
  "/welcome", "/auth/login", "/auth/register", "/api/vars/lookup", "/api/kv/automation", "/api/health/live", "/api/health/ready", "/api/cluster/info", "/favicon.ico",
  // Public welcome illustrations; keep other image paths authenticated.
  "/images/screenshots/deploy.webp",
  "/images/screenshots/flux.webp",
  "/images/screenshots/dashboard.webp",
  "/images/screenshots/secrets.webp",
];
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
    // Invoke the existing metadata GET only after this request's fresh admission.
    if (request.method === "GET" && pathname === "/api/cluster/pods") {
      const response = await getPodMetadata(request);
      // Keep private metadata uncached and avoid a second response transform.
      response.headers.set("Cache-Control", request.headers.get("accept-encoding")?.includes(";")
        ? "no-store" : "no-store, no-transform");
      return response;
    }
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
