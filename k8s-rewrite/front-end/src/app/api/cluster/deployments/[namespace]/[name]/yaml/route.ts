import { validateNamespace, validateResourceName, KubernetesCommandError } from "@/lib/k8s";
import { clusterRoute } from "@/lib/cluster-http";
import { NextRequest, NextResponse } from "next/server";
import { kubectlExec } from "@/lib/k8s";
import { writeFile, unlink } from "fs/promises";
import { randomUUID } from "crypto";
import { tmpdir } from "os";
import { join } from "path";
import { requireWrite } from "@/lib/permissions";
export async function GET(_request: NextRequest, { params }: {
    params: Promise<{
        namespace: string;
        name: string;
    }>;
}) {
    return clusterRoute(async () => {
        const { namespace: rawNamespace, name: rawName } = await params;
        const namespace = validateNamespace(rawNamespace), name = validateResourceName(rawName);
        const yaml = await kubectlExec(["get", "deployment", (validateResourceName(name)), "-n", (validateNamespace(namespace)), "-o", "yaml"], 10000);
        if (!yaml) {
            return NextResponse.json({ error: "Failed to get YAML" }, { status: 500 });
        }
        return NextResponse.json({ yaml });
    });
}
export async function PUT(request: NextRequest, { params }: {
    params: Promise<{
        namespace: string;
        name: string;
    }>;
}) {
    return clusterRoute(async () => {
        const auth = await requireWrite();
        if (auth instanceof NextResponse)
            return auth;
        const { namespace: rawNamespace, name: rawName } = await params;
        const namespace = validateNamespace(rawNamespace), name = validateResourceName(rawName);
        try {
            const { yaml } = await request.json();
            if (!yaml || typeof yaml !== "string") {
                return NextResponse.json({ error: "No YAML body" }, { status: 400 });
            }
            // Write to temp file then apply
            const tmpPath = join(tmpdir(), `k8s-edit-${randomUUID()}.yaml`);
            await writeFile(tmpPath, yaml);
            try {
                const result = await kubectlExec(["apply", "-f", (tmpPath)], 15000);
                return NextResponse.json({ success: true });
            }
            finally {
                await unlink(tmpPath).catch(() => { });
            }
        }
        catch (error) {
            if (error instanceof KubernetesCommandError)
                throw error;
            return NextResponse.json({ error: "Invalid request" }, { status: 400 });
        }
    });
}
