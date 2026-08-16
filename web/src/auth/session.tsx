import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, getToken, setToken } from "@/lib/api";
import type { User } from "@/lib/types";

const HH_KEY = "relay.householdId";

interface SessionValue {
  user: User | null;
  loading: boolean;
  householdId: string | null;
  setHouseholdId: (id: string | null) => void;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [householdId, setHouseholdIdState] = useState<string | null>(
    () => localStorage.getItem(HH_KEY),
  );
  const qc = useQueryClient();

  const setHouseholdId = useCallback((id: string | null) => {
    setHouseholdIdState(id);
    if (id) localStorage.setItem(HH_KEY, id);
    else localStorage.removeItem(HH_KEY);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setToken(null);
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const signIn = useCallback(
    async (token: string) => {
      setToken(token);
      await refreshUser();
      qc.invalidateQueries();
    },
    [refreshUser, qc],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
    setHouseholdId(null);
    qc.clear();
  }, [qc, setHouseholdId]);

  const value = useMemo(
    () => ({ user, loading, householdId, setHouseholdId, signIn, signOut, refreshUser }),
    [user, loading, householdId, setHouseholdId, signIn, signOut, refreshUser],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSession(): SessionValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useSession outside provider");
  return v;
}
