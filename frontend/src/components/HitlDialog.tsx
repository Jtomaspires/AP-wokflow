import { AlertTriangle, Check, LoaderCircle } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { TicketDetail } from "@/types/ticket";

export function HitlDialog({
  open,
  onOpenChange,
  detail,
  draftEdit,
  onDraftChange,
  healthOk,
  busy,
  error,
  onApprove,
  onEscalate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail: TicketDetail | null;
  draftEdit: string;
  onDraftChange: (value: string) => void;
  healthOk: boolean;
  busy: boolean;
  error: string | null;
  onApprove: () => Promise<boolean>;
  onEscalate: () => Promise<boolean>;
}) {
  const draft = detail?.draft ?? null;
  const edited = Boolean(draft && draftEdit !== draft.generated_text);
  const approveDisabled = !draft || !healthOk || busy;

  async function approve() {
    if (await onApprove()) {
      onOpenChange(false);
      toast.success("Approved — reply sent");
    }
  }

  async function escalate() {
    if (await onEscalate()) {
      onOpenChange(false);
      toast("Escalated");
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Review & decide</DialogTitle>
          <DialogDescription>
            {draft ? `To: ${draft.to_email} (${draft.target})` : "No draft is available for this case."}
          </DialogDescription>
        </DialogHeader>

        {draft ? (
          <div className="space-y-2">
            <Textarea
              className="min-h-52 resize-y"
              value={draftEdit}
              onChange={(event) => onDraftChange(event.target.value)}
              disabled={busy}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{draftEdit.length} characters</span>
              {edited && <Badge variant="secondary">Edited</Badge>}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            This case needs a human decision. Escalate it instead of sending an unverified reply.
          </div>
        )}

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <DialogFooter className="sm:justify-between">
          <Button
            variant="outline"
            className="border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
            onClick={() => void escalate()}
            disabled={!healthOk || busy}
          >
            {busy ? <LoaderCircle className="animate-spin" /> : <AlertTriangle />}
            Escalate
          </Button>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <Button
                  className="bg-emerald-600 text-white hover:bg-emerald-700"
                  onClick={() => void approve()}
                  disabled={approveDisabled}
                >
                  {busy ? <LoaderCircle className="animate-spin" /> : <Check />}
                  Approve & send
                </Button>
              </span>
            </TooltipTrigger>
            {!draft && <TooltipContent>No draft to send — escalate instead</TooltipContent>}
          </Tooltip>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
