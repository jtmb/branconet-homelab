import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { getKustomizationDetail } from "@/lib/flux";
export async function GET(_request: NextRequest, { params }: {
    params: Promise<{
        name: string;
    }>;
}) {
    try {
        const { name } = await params;
        const detail = await getKustomizationDetail(decodeURIComponent(name));
        if (!detail) {
            return NextResponse.json({ error: "Kustomization not found" }, { status: 404 });
        }
        return NextResponse.json(detail);
    }
    catch (err) {
        return clusterRoute(async () => { throw err; });
    }
}
