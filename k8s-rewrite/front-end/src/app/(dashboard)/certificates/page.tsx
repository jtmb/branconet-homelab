import CertificatesScreen from "./certificates-screen";
import { getOperatorRole } from "@/lib/permissions";

export default async function CertificatesPage() {
  return <CertificatesScreen canManage={await getOperatorRole() === "write"} />;
}
