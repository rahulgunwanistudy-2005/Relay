// Thin fetch client for the real Relay API. One place holds the bearer token.

import type {
  AcceptResponse,
  DraftResponse,
  GhostQueueItem,
  HandoffContract,
  Household,
  IncomingHandoff,
  InviteResponse,
  Member,
  OwnershipEvent,
  ProofOfRelief,
  Responsibility,
  ResponsibilitySummary,
  StepDraft,
  TokenResponse,
  User,
} from "./types";

const TOKEN_KEY = "relay.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => (d?.msg ? d.msg : JSON.stringify(d))).join("; ")
          : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, message);
  }
  return payload as T;
}

export const api = {
  // Auth
  register: (email: string, password: string, display_name: string) =>
    request<TokenResponse>("POST", "/v1/auth/register", { email, password, display_name }),
  login: (email: string, password: string) =>
    request<TokenResponse>("POST", "/v1/auth/login", { email, password }),
  me: () => request<User>("GET", "/v1/me"),

  // Households
  listHouseholds: () => request<Household[]>("GET", "/v1/households"),
  createHousehold: (name: string, timezone: string) =>
    request<Household>("POST", "/v1/households", { name, timezone }),
  getHousehold: (id: string) => request<Household>("GET", `/v1/households/${id}`),
  members: (id: string) => request<Member[]>("GET", `/v1/households/${id}/members`),
  invite: (id: string, email?: string) =>
    request<InviteResponse>("POST", `/v1/households/${id}/invites`, { email: email ?? null }),
  acceptInvite: (token: string) =>
    request<{ household_id: string }>("POST", `/v1/invites/${token}/accept`),

  // Responsibilities
  draft: (householdId: string, text: string) =>
    request<DraftResponse>("POST", `/v1/responsibilities/drafts?household_id=${householdId}`, {
      text,
    }),
  createResponsibility: (
    householdId: string,
    body: {
      title: string;
      domain: string;
      completion_standard: string | null;
      target_at: string | null;
      recurrence_rrule: string | null;
      steps: Array<{
        step_key: string;
        kind: string;
        description: string;
        ordering: number;
        due_at: string | null;
        provenance: string;
        is_assumption: boolean;
      }>;
    },
  ) =>
    request<Responsibility>("POST", `/v1/responsibilities?household_id=${householdId}`, body),
  listResponsibilities: (householdId: string) =>
    request<ResponsibilitySummary[]>(
      "GET",
      `/v1/responsibilities?household_id=${householdId}`,
    ),
  getResponsibility: (id: string) =>
    request<Responsibility>("GET", `/v1/responsibilities/${id}`),
  completeStep: (rid: string, sid: string) =>
    request<unknown>("POST", `/v1/responsibilities/${rid}/steps/${sid}/complete`),
  reopenStep: (rid: string, sid: string) =>
    request<unknown>("POST", `/v1/responsibilities/${rid}/steps/${sid}/reopen`),

  // Handoff
  proposeHandoff: (rid: string, target_membership_id: string) =>
    request<HandoffContract>("POST", `/v1/responsibilities/${rid}/handoffs`, {
      target_membership_id,
    }),
  getHandoff: (cid: string) => request<HandoffContract>("GET", `/v1/handoffs/${cid}`),
  acceptHandoff: (cid: string, idempotency_key: string) =>
    request<AcceptResponse>("POST", `/v1/handoffs/${cid}/accept`, { idempotency_key }),
  declineHandoff: (cid: string) =>
    request<HandoffContract>("POST", `/v1/handoffs/${cid}/decline`),
  incomingHandoffs: () => request<IncomingHandoff[]>("GET", "/v1/me/handoffs"),

  // Load & proof
  ghostQueue: () => request<GhostQueueItem[]>("GET", "/v1/me/ghost-queue"),
  proof: (rid: string) =>
    request<ProofOfRelief>("GET", `/v1/responsibilities/${rid}/proof-of-relief`),
  ownershipHistory: (rid: string) =>
    request<OwnershipEvent[]>("GET", `/v1/responsibilities/${rid}/ownership-history`),
};

export type { StepDraft };
