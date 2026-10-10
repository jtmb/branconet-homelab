import { getCurrentRole } from "@/lib/permissions";
import SecretsEditor from "./secrets-editor";
export const dynamic = "force-dynamic";
export default async function SecretsPage() {
  return <SecretsEditor canWrite={(await getCurrentRole()) === "write"} />;
}
