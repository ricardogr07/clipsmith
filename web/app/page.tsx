import { DashboardClient } from "@/components/DashboardClient";

export const dynamic = "force-dynamic";

export default function Page() {
  if (process.env.MAINTENANCE_MODE === "true") {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold">Service is paused</p>
          <p className="text-sm text-muted-foreground">The pipeline is offline. Check back soon.</p>
        </div>
      </main>
    );
  }

  return <DashboardClient />;
}
