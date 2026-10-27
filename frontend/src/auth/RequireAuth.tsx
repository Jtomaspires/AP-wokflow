import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/auth/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="grid min-h-screen place-items-center bg-muted/30 p-6">
        <div className="w-full max-w-sm space-y-4">
          <Skeleton className="mx-auto size-12 rounded-xl" />
          <Skeleton className="mx-auto h-7 w-40" />
          <Skeleton className="mx-auto h-4 w-64" />
        </div>
      </div>
    );
  }
  if (status === "anon") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}
