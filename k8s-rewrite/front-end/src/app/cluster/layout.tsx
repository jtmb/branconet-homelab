import ClusterSidebar from "./sidebar";
import TopNav from "./topnav";

export default function ClusterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-zinc-950 flex">
      <ClusterSidebar />
      <div className="flex-1 min-w-0 flex flex-col">
        <TopNav />
        <div className="flex-1">{children}</div>
      </div>
    </div>
  );
}
