import { NextResponse } from "next/server";
import { getFluxHierarchy } from "@/lib/flux";

export async function GET() {
  try {
    const trees = await getFluxHierarchy();
    return NextResponse.json({ trees });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
