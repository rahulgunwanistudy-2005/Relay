import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export function useHouseholds(enabled = true) {
  return useQuery({ queryKey: ["households"], queryFn: api.listHouseholds, enabled });
}

export function useMembers(householdId: string | null) {
  return useQuery({
    queryKey: ["members", householdId],
    queryFn: () => api.members(householdId!),
    enabled: !!householdId,
  });
}

export function useResponsibilities(householdId: string | null) {
  return useQuery({
    queryKey: ["responsibilities", householdId],
    queryFn: () => api.listResponsibilities(householdId!),
    enabled: !!householdId,
  });
}

export function useResponsibility(id: string | undefined) {
  return useQuery({
    queryKey: ["responsibility", id],
    queryFn: () => api.getResponsibility(id!),
    enabled: !!id,
  });
}

export function useGhostQueue() {
  return useQuery({ queryKey: ["ghost-queue"], queryFn: api.ghostQueue });
}

export function useIncomingHandoffs() {
  return useQuery({ queryKey: ["incoming-handoffs"], queryFn: api.incomingHandoffs });
}

export function useProof(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["proof", id],
    queryFn: () => api.proof(id!),
    enabled: !!id && enabled,
  });
}

export function useHistory(id: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["history", id],
    queryFn: () => api.ownershipHistory(id!),
    enabled: !!id && enabled,
  });
}
