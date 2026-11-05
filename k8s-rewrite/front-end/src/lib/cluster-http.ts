import { NextResponse } from "next/server";
import { KubernetesCommandError } from "./kubectl-client";

export async function clusterRoute(operation: () => Promise<Response>) {
  try { return await operation(); }
  catch (error) {
    if (error instanceof KubernetesCommandError)
      return NextResponse.json({ error: error.message }, { status: error.status });
    if (error instanceof SyntaxError)
      return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
    return NextResponse.json({ error: "Cluster operation unavailable" }, { status: 503 });
  }
}
