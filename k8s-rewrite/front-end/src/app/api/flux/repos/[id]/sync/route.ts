import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { syncRepo } from "@/lib/flux";
import { requireOperator } from "@/lib/permissions";
export async function POST(request: NextRequest, { params }: {
    params: Promise<{
        id: string;
    }>;
}) {
    const auth = await requireOperator();
    if (auth instanceof NextResponse)
        return auth;
    try {
        const { id } = await params;
        const url = new URL(request.url);
        const result = await syncRepo(id, url.searchParams.get("name") ?? undefined, url.searchParams.get("namespace") ?? undefined);
        if (!result.success) {
            return NextResponse.json({ error: result.error }, { status: 400 });
        }
        return NextResponse.json({ success: true });
    }
    catch (err) {
        return clusterRoute(async () => { throw err; });
    }
}
