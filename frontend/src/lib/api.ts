import type {
  ApproveResponse,
  EscalateResponse,
  Stats,
  Ticket,
  TicketDetail,
  TicketStatus,
} from "../types/ticket";
import type { Operator } from "../types/auth";

const BASE = (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "API unreachable");
  }

  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : response.statusText;
    if (response.status === 401 && path !== "/auth/login" && path !== "/auth/me") {
      onUnauthorized?.();
    }
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

export async function getHealth(): Promise<{ status: string }> {
  return request("/health");
}

export async function getStats(): Promise<Stats> {
  return request("/stats");
}

export async function getTickets(status?: TicketStatus): Promise<Ticket[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request(`/tickets${query}`);
}

export async function getTicket(id: string): Promise<TicketDetail> {
  return request(`/tickets/${id}`);
}

export function login(email: string, password: string): Promise<Operator> {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function logout(): Promise<void> {
  return request("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<Operator> {
  return request("/auth/me");
}

export async function approveTicket(
  id: string,
  body: { final_text?: string },
): Promise<ApproveResponse> {
  const payload: { final_text?: string } = {};
  if (body.final_text !== undefined) {
    payload.final_text = body.final_text;
  }
  return request(`/tickets/${id}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function escalateTicket(id: string): Promise<EscalateResponse> {
  return request(`/tickets/${id}/escalate`, {
    method: "POST",
  });
}
