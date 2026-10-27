import { LogOut, RefreshCw } from "lucide-react";

import { useAuth } from "@/auth/AuthContext";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Stats } from "@/types/ticket";

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function AppHeader({
  stats,
  healthOk,
  refreshing,
  onRefresh,
}: {
  stats: Stats;
  healthOk: boolean;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const { operator, logout } = useAuth();
  const awaiting = stats.awaiting_human ?? 0;

  return (
    <header className="flex min-h-16 shrink-0 flex-wrap items-center gap-4 border-b bg-background px-4 py-2 md:px-6">
      <div className="min-w-40">
        <p className="font-semibold tracking-tight">P2P AP</p>
        <p className="text-xs text-muted-foreground">Operator console</p>
      </div>

      <div className="flex flex-1 items-baseline justify-center gap-2">
        <span className={awaiting > 0 ? "text-2xl font-semibold text-amber-600" : "text-2xl font-semibold"}>
          {awaiting}
        </span>
        <span className="text-sm text-muted-foreground">awaiting review</span>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant="outline" className="gap-2">
          <span className="relative flex size-2">
            {healthOk && (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            )}
            <span className={`relative inline-flex size-2 rounded-full ${healthOk ? "bg-emerald-500" : "bg-red-500"}`} />
          </span>
          {healthOk ? "API live" : "API down"}
        </Badge>
        <Button variant="outline" size="sm" onClick={onRefresh} disabled={refreshing}>
          <RefreshCw className={refreshing ? "animate-spin" : ""} />
          <span className="hidden sm:inline">Refresh</span>
        </Button>

        {operator && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="h-auto gap-2 px-2 py-1.5">
                <Avatar size="sm">
                  <AvatarFallback>{initials(operator.display_name)}</AvatarFallback>
                </Avatar>
                <span className="hidden text-left md:block">
                  <span className="block text-sm font-medium">{operator.display_name}</span>
                  <span className="block text-xs font-normal text-muted-foreground">{operator.email}</span>
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => void logout()}>
                <LogOut />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
