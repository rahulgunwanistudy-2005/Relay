import { useState } from "react";
import "./household.css";
import { api } from "@/lib/api";
import { useSession } from "@/auth/session";
import { useHouseholds, useMembers } from "@/lib/queries";
import { Avatar, Banner, Button, Field } from "@/components/ui";

export function HouseholdView() {
  const { householdId } = useSession();
  const households = useHouseholds();
  const members = useMembers(householdId);
  const active = households.data?.find((h) => h.id === householdId);

  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    if (!householdId) return;
    setPending(true);
    setError(null);
    setInviteLink(null);
    try {
      const res = await api.invite(householdId, email.trim() || undefined);
      // The token is the shareable claim. In a real deploy this is emailed; here we surface it.
      setInviteLink(`${window.location.origin}/?invite=${res.token}`);
      setEmail("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create invite");
    } finally {
      setPending(false);
    }
  }

  async function copy() {
    if (!inviteLink) return;
    await navigator.clipboard.writeText(inviteLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="hh">
      <header className="hh__head">
        <p className="label">Household</p>
        <h1 className="hh__title display">{active?.name ?? "Your household"}</h1>
        <p className="hh__sub">
          Everyone here can be handed a responsibility — and can hand one back, by consent.
        </p>
      </header>

      <section className="hh__members" aria-labelledby="mem-h">
        <h2 id="mem-h" className="label hh__sectionhead">
          People
        </h2>
        <ul className="hh__list">
          {members.data?.map((m) => (
            <li key={m.id} className="hh__member">
              <Avatar name={m.display_name} muted={m.role === "member"} />
              <span className="hh__member-body">
                <span className="hh__member-name">{m.display_name}</span>
                <span className="hh__member-email">{m.email}</span>
              </span>
              <span className="hh__member-role label">{m.role}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="hh__invite" aria-labelledby="inv-h">
        <h2 id="inv-h" className="label hh__sectionhead">
          Invite someone
        </h2>
        <form className="hh__inviteform" onSubmit={invite}>
          <Field label="Their email (optional)" id="invite-email">
            <input
              id="invite-email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="partner@home.example"
            />
          </Field>
          <Button type="submit" pending={pending}>
            Create invite
          </Button>
        </form>
        {error && <Banner tone="error">{error}</Banner>}
        {inviteLink && (
          <div className="hh__link">
            <p className="hh__link-note">
              Share this link. When they open it signed in, they join this household.
            </p>
            <div className="hh__link-row">
              <code className="hh__link-code">{inviteLink}</code>
              <Button variant="ghost" onClick={copy} confirmed={copied}>
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
