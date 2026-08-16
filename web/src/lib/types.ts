// Shapes mirror the real Relay API responses (verified against the live server).

export type UUID = string;

export type LifecycleKind =
  | "anticipate"
  | "options"
  | "decide"
  | "prepare"
  | "execute"
  | "verify"
  | "follow_up"
  | "recur";

export type Provenance = "user_explicit" | "ai_inferred" | "deterministic";
export type StepStatus = "pending" | "in_progress" | "done" | "blocked" | "skipped";
export type ResponsibilityStatus =
  | "draft"
  | "proposed"
  | "active"
  | "blocked"
  | "transfer_pending"
  | "completed"
  | "archived";

export interface User {
  id: UUID;
  email: string;
  display_name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: UUID;
}

export interface Household {
  id: UUID;
  name: string;
  timezone: string;
}

export interface Member {
  id: UUID; // membership id
  user_id: UUID;
  household_id: UUID;
  role: "owner" | "admin" | "member";
  is_active: boolean;
  display_name: string;
  email: string;
}

export interface InviteResponse {
  invite_id: UUID;
  token: string;
  household_id: UUID;
  expires_at: string;
}

export interface StepDraft {
  step_key: string;
  kind: LifecycleKind;
  description: string;
  provenance: Provenance;
  confidence: number | null;
  is_assumption: boolean;
  due_at: string | null;
}

export interface DraftResponse {
  title: string;
  domain: string;
  people: string[];
  deadline_text: string | null;
  deadline_at: string | null;
  recurrence_rrule: string | null;
  steps: StepDraft[];
  completion_standard: string | null;
  assumptions: string[];
  clarification_questions: string[];
  field_provenance: Record<string, Provenance>;
  confidence: number | null;
  validation_state: string;
  provider: string;
}

export interface Step {
  id: UUID;
  step_key: string;
  kind: LifecycleKind;
  description: string;
  ordering: number;
  status: StepStatus;
  due_at: string | null;
  provenance: Provenance;
  is_assumption: boolean;
}

export interface Cycle {
  id: UUID;
  sequence: number;
  status: string;
  starts_at: string | null;
  target_at: string | null;
  completed_at: string | null;
  steps: Step[];
}

export interface Recurrence {
  rrule: string;
  timezone: string;
  next_materialization_at: string | null;
  enabled: boolean;
}

export interface Responsibility {
  id: UUID;
  household_id: UUID;
  title: string;
  domain: string;
  status: ResponsibilityStatus;
  scope_version: number;
  ownership_version: number;
  current_owner_membership_id: UUID | null;
  completion_standard: string | null;
  current_cycle: Cycle | null;
  recurrence: Recurrence | null;
}

export interface ResponsibilitySummary {
  id: UUID;
  title: string;
  status: ResponsibilityStatus;
  current_owner_membership_id: UUID | null;
  ownership_version: number;
}

export interface HandoffContract {
  id: UUID;
  responsibility_id: UUID;
  status: string;
  source_owner_membership_id: UUID | null;
  proposed_owner_membership_id: UUID;
  expected_scope_version: number;
  expected_ownership_version: number;
}

export interface AcceptResponse {
  responsibility_id: UUID;
  new_owner_membership_id: UUID;
  ownership_version: number;
  reminders_rerouted: number;
  replayed: boolean;
}

export interface IncomingHandoff {
  contract_id: UUID;
  responsibility_id: UUID;
  responsibility_title: string;
  status: string;
  proposer_display_name: string;
  proposer_membership_id: UUID;
  proposed_owner_membership_id: UUID;
  created_at: string;
}

export interface GhostQueueItem {
  reminder_id: UUID;
  responsibility_id: UUID;
  reminder_type: "step_due" | "cycle_due" | "overdue" | "escalation";
  scheduled_for: string;
}

export interface ProofOfRelief {
  responsibility_id: UUID;
  transferred: boolean;
  ownership_version_before: number | null;
  ownership_version_after: number | null;
  new_owner_membership_id: UUID | null;
  at: string | null;
  reminders_rerouted: number;
  lifecycle_obligations_transferred: number;
  decision_points_transferred: number;
  recurrence_obligations_transferred: number;
}

export interface OwnershipEvent {
  id: UUID;
  event_type: string;
  actor_membership_id: UUID | null;
  previous_owner_membership_id: UUID | null;
  new_owner_membership_id: UUID | null;
  ownership_version: number;
  created_at: string;
}
