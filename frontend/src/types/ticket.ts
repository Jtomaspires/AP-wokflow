export type TicketStatus =
  | "open"
  | "awaiting_human"
  | "awaiting_sender_reply"
  | "resolved"
  | "escalated"
  | "quarantined"
  | "discarded"
  | "delegated";

export type Intent =
  | "payment_status"
  | "delay_reason"
  | "future_timing"
  | "unknown";

export type DraftTarget =
  | "sender"
  | "invoicing"
  | "payments"
  | "approval_owners";

export interface Ticket {
  id: string;
  thread_id: string;
  message_id: string;
  sender_email: string;
  subject: string;
  body: string;
  received_at: string;
  status: TicketStatus;
  is_ap: boolean | null;
  intent: Intent | null;
  language: string | null;
  assigned_operator_id: string | null;
  confidence: number | null;
  is_thread_continuation: boolean;
  created_at: string;
  updated_at: string;
}

export interface Sender {
  id: string;
  email: string;
  name: string;
  company: string;
  vendor_sap_id: string | null;
  sender_type: string;
  created_at: string;
}

export interface Invoice {
  invoice_ref: string;
  supplier_name: string;
  amount: string | number;
  stage: string;
  currency: string;
  status: string | null;
  sap_id: string | null;
  company_code: string | null;
  payment_blocking_reason: string | null;
  approval_step: string | null;
  due_date: string | null;
  approval_owner_email: string | null;
  clearing_document: string | null;
  payment_document: string | null;
  payment_date: string | null;
  payment_proof_ref: string | null;
}

export interface Draft {
  id: string;
  ticket_id: string;
  target: DraftTarget;
  to_email: string;
  generated_text: string;
  final_text: string | null;
  edited_by_human: boolean;
  operator_notes: string | null;
  attach_invoice_pdf: boolean;
  attach_payment_proof: boolean;
  created_at: string;
}

export interface AuditSummary {
  node: string;
  action: string;
  metadata: Record<string, unknown>;
}

export interface TicketDetail extends Ticket {
  sender: Sender | null;
  draft: Draft | null;
  invoice: Invoice | null;
  audit: AuditSummary[];
}

export type Stats = Record<string, number>;

export interface ApproveResponse {
  ticket_id?: string;
  stop_reason?: string;
  status?: string;
}

export interface EscalateResponse {
  ticket_id: string;
  status: string;
  should_stop?: boolean;
}
