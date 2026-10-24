"use client";
import { useState } from "react";
import dynamic from "next/dynamic";
import { MoreHorizontal } from "lucide-react";
import type { ResourceActionProps } from "./resource-actions-menu";
const Menu = dynamic(() => import("./resource-actions-menu"), { ssr: false, loading: () => <span role="status" className="text-xs">Loading actions…</span> });
export default function ResourceActionsTrigger(props: ResourceActionProps) {
  const [loaded, setLoaded] = useState(false);
  if (loaded) return <Menu {...props} initialOpen />;
  const name = props.resource.metadata?.name ?? props.resource.name ?? "";
  return <button onClick={() => setLoaded(true)} aria-label={`Actions for ${name}`} className="rounded-lg p-2 hover:bg-zinc-800"><MoreHorizontal className="h-5 w-5" /></button>;
}
