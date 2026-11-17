import CertificatesScreen from "./certificates-screen";
import { getCurrentRole } from "@/lib/permissions";

export default async function CertificatesPage() {
  return <CertificatesScreen canManage={await getCurrentRole() === "write"} />;
}
