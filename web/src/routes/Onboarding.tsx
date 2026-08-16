import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import "./auth.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { Banner, Button, Field } from "@/components/ui";

const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

export function Onboarding() {
  const { setHouseholdId } = useSession();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setPending(true);
    try {
      const hh = await api.createHousehold(name.trim() || "My household", TZ);
      await qc.invalidateQueries({ queryKey: ["households"] });
      setHouseholdId(hh.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create household");
      setPending(false);
    }
  }

  return (
    <div className="auth">
      <form className="auth__form" style={{ maxWidth: 460 }} onSubmit={create}>
        <p className="label">First, a household</p>
        <h1 className="display" style={{ fontSize: 30, letterSpacing: "-0.02em" }}>
          Who shares the load?
        </h1>
        <p className="auth__fine" style={{ fontSize: 14 }}>
          A household is the shared space where responsibilities live and move between people.
          You can invite someone right after.
        </p>
        <Field label="Household name" id="hh">
          <input
            id="hh"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="The Rivera household"
            autoFocus
          />
        </Field>
        {error && <Banner tone="error">{error}</Banner>}
        <Button type="submit" pending={pending}>
          Create household
        </Button>
      </form>
    </div>
  );
}
