import { Link } from "react-router-dom";
import "./inbox.css";
import { useIncomingHandoffs } from "@/lib/queries";
import { firstName, relativeTime } from "@/lib/format";

export function Inbox() {
  const inbox = useIncomingHandoffs();

  return (
    <div className="inbox">
      <header className="inbox__head">
        <p className="label">Incoming</p>
        <h1 className="inbox__title display">Responsibilities offered to you</h1>
        <p className="inbox__lead">
          Nothing here is yours until you open the contract and accept. That's the whole
          point — ownership moves by consent, not by assignment.
        </p>
      </header>

      {inbox.isLoading ? (
        <p className="inbox__calm">Checking…</p>
      ) : (inbox.data?.length ?? 0) === 0 ? (
        <div className="inbox__empty">
          <p className="inbox__empty-line display">No one is handing you anything right now.</p>
          <p className="inbox__calm">When someone proposes a transfer, it will wait here.</p>
        </div>
      ) : (
        <ul className="inbox__list">
          {inbox.data!.map((h) => (
            <li key={h.contract_id}>
              <Link to={`/handoff/${h.contract_id}`} className="inbox__row">
                <span className="inbox__thread" aria-hidden />
                <span className="inbox__body">
                  <span className="inbox__from">
                    {firstName(h.proposer_display_name)} wants to hand you
                  </span>
                  <span className="inbox__resp">{h.responsibility_title}</span>
                </span>
                <span className="inbox__meta">
                  <span className="inbox__when">{relativeTime(h.created_at)}</span>
                  <span className="inbox__cta">Review contract →</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
