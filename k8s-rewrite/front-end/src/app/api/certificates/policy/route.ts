import { requireWrite } from "@/lib/permissions";
import { kubectlJSON } from "@/lib/k8s";
import { certificatePolicyResponse } from "@/lib/certificate-control";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(request: Request) {
  return certificatePolicyResponse(request, {
    authorize: requireWrite,
    read: args => kubectlJSON(args, 10000),
    patch: args => kubectlJSON(args, 10000),
  });
}
