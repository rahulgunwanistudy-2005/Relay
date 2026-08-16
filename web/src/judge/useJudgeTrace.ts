import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { memberName } from "@/lib/format";
import type {
  Member,
  OwnershipEvent,
  ProofOfRelief,
  Responsibility,
} from "@/lib/types";

export interface JudgeTrace {
  responsibility: Responsibility;
  proof: ProofOfRelief;
  history: OwnershipEvent[];
  members: Member[];
  sourceName: string;
  recipientName: string;
  sentence: string;
}

export type JudgeTraceResult =
  | { status: "ready"; trace: JudgeTrace }
  | { status: "none" }
  | { status: "empty" };

/**
 * Assembles a Judge Mode trace from real persisted state: it scans the
 * household's responsibilities for one that was actually transferred (proof
 * says so) and gathers its lifecycle, proof, and ownership history. If nothing
 * has genuinely been handed over, it returns "none" — Judge Mode then refuses
 * to invent a story.
 */
export function useJudgeTrace(householdId: string | null) {
  return useQuery<JudgeTraceResult>({
    queryKey: ["judge-trace", householdId],
    enabled: !!householdId,
    staleTime: 0,
    queryFn: async () => {
      const [summaries, members] = await Promise.all([
        api.listResponsibilities(householdId!),
        api.members(householdId!),
      ]);
      if (summaries.length === 0) return { status: "empty" };

      const proofs = await Promise.all(
        summaries.map((s) =>
          api
            .proof(s.id)
            .then((p) => ({ id: s.id, proof: p }))
            .catch(() => null),
        ),
      );
      const transferred = proofs
        .filter((x): x is { id: string; proof: ProofOfRelief } => !!x && x.proof.transferred)
        .sort(
          (a, b) =>
            new Date(b.proof.at ?? 0).getTime() - new Date(a.proof.at ?? 0).getTime(),
        );

      if (transferred.length === 0) return { status: "none" };

      const chosen = transferred[0];
      const [responsibility, history] = await Promise.all([
        api.getResponsibility(chosen.id),
        api.ownershipHistory(chosen.id),
      ]);

      const created = history.find((e) => e.event_type === "created");
      const sourceMembershipId =
        chosen.proof.new_owner_membership_id &&
        (history.find((e) => e.event_type === "transferred")?.previous_owner_membership_id ??
          created?.new_owner_membership_id ??
          null);

      return {
        status: "ready",
        trace: {
          responsibility,
          proof: chosen.proof,
          history,
          members,
          sourceName: memberName(members, sourceMembershipId ?? null),
          recipientName: memberName(members, chosen.proof.new_owner_membership_id),
          sentence: responsibility.title,
        },
      };
    },
  });
}
