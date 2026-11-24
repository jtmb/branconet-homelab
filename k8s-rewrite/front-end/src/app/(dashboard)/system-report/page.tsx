import { getOperatorRole } from "@/lib/permissions";
import SystemReportScreen from "./system-report-screen";

export default async function SystemReportPage() {
  return <SystemReportScreen canScan={await getOperatorRole() === "write"} />;
}
