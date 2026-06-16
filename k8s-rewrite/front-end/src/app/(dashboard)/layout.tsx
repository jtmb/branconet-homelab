import ClusterSidebar from "./sidebar";
import TopNav from "./topnav";
import ShellContainer from "@/components/cluster/shell-container";

export default function ClusterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-zinc-950 flex">
      <ClusterSidebar />
      <div className="relative flex-1 min-w-0 flex flex-col">
        <TopNav />
        <ShellContainer />
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}
