import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "./lib/api";
import { useSession } from "./auth/session";
import { useHouseholds } from "./lib/queries";
import { Shell } from "./components/Shell";
import { AuthScreen } from "./routes/AuthScreen";
import { Onboarding } from "./routes/Onboarding";
import { MyLoad } from "./routes/MyLoad";
import { Capture } from "./routes/Capture";
import { XRay } from "./routes/XRay";
import { Inbox } from "./routes/Inbox";
import { Contract } from "./routes/Contract";
import { HouseholdView } from "./routes/Household";
import { JudgeMode } from "./judge/JudgeMode";

export function App() {
  const { user, loading, householdId, setHouseholdId } = useSession();
  const households = useHouseholds(!!user);
  const [judge, setJudge] = useState(false);
  const location = useLocation();
  const qc = useQueryClient();

  // Redeem an invite link (?invite=token) once the user is signed in.
  useEffect(() => {
    if (!user) return;
    const params = new URLSearchParams(window.location.search);
    const token = params.get("invite");
    if (!token) return;
    (async () => {
      try {
        const res = await api.acceptInvite(token);
        await qc.invalidateQueries({ queryKey: ["households"] });
        setHouseholdId(res.household_id);
      } catch {
        /* already a member or invalid — silently drop the token */
      } finally {
        params.delete("invite");
        const qs = params.toString();
        window.history.replaceState({}, "", window.location.pathname + (qs ? `?${qs}` : ""));
      }
    })();
  }, [user, qc, setHouseholdId]);

  // Adopt a household automatically when exactly the natural choice exists.
  useEffect(() => {
    if (!households.data) return;
    const ids = households.data.map((h) => h.id);
    if (householdId && !ids.includes(householdId)) setHouseholdId(null);
    if (!householdId && ids.length > 0) setHouseholdId(ids[0]);
  }, [households.data, householdId, setHouseholdId]);

  // Keyboard shortcut: J toggles Judge Mode (ignoring text fields).
  const openJudge = useCallback(() => setJudge(true), []);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (e.key === "j" || e.key === "J") setJudge((v) => !v);
      if (e.key === "Escape") setJudge(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (loading) return <Splash />;
  if (!user) return <AuthScreen />;

  const hasHousehold = (households.data?.length ?? 0) > 0;
  if (households.isSuccess && !hasHousehold) return <Onboarding />;

  return (
    <>
      <Shell onJudge={openJudge} dimmed={judge}>
        <Routes location={location}>
          <Route path="/" element={<MyLoad onJudge={openJudge} />} />
          <Route path="/new" element={<Capture />} />
          <Route path="/r/:id" element={<XRay />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/handoff/:contractId" element={<Contract />} />
          <Route path="/household" element={<HouseholdView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Shell>
      <AnimatePresence>
        {judge && <JudgeMode onExit={() => setJudge(false)} />}
      </AnimatePresence>
    </>
  );
}

function Splash() {
  return (
    <div
      style={{
        height: "100%",
        display: "grid",
        placeItems: "center",
        color: "var(--ink-2)",
        fontFamily: "var(--font-display)",
        fontSize: 22,
      }}
    >
      Relay
    </div>
  );
}
