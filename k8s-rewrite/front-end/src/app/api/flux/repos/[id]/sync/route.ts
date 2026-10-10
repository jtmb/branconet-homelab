import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { syncRepo } from "@/lib/flux";
import { requireOperator } from "@/lib/permissions";
export async function POST(_request: NextRequest, { params }: {
    params: Promise<{
        id: string;
    }>;
}) {
    const auth = await requireOperator();
    if (auth instanceof NextResponse)
        return auth;
    try {
        const { id } = await params;
        const result = await syncRepo(id);
        if (!result.success) {
            return NextResponse.json({ error: result.error }, { status: 400 });
        }
        return NextResponse.json({ success: true });
    }
    catch (err) {
        return clusterRoute(async () => { throw err; });
    }
}
