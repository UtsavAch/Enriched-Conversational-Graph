import {
  useConfirmEntityTypeSuggestion,
  useEntityTypeSuggestions,
  useRejectEntityTypeSuggestion,
} from "@/api/queries";
import { Button } from "@/components/Button";
import "./EntityTypeSuggestions.css";

/**
 * Non-blocking "new entity type?" suggestions (evaluation_report.md section 8).
 *
 * W1 can propose a type when nothing in the conversation's current vocabulary
 * fits (`propose:<label>`), rather than forcing every domain-specific entity
 * into "other". This renders nothing when there's nothing pending — it's a
 * quiet badge a user acts on whenever convenient, never a modal that
 * interrupts the chat.
 */
export function EntityTypeSuggestions({
  conversationId,
}: {
  conversationId: string | null;
}) {
  const { data: suggestions } = useEntityTypeSuggestions(conversationId);
  const confirm = useConfirmEntityTypeSuggestion(conversationId);
  const reject = useRejectEntityTypeSuggestion(conversationId);

  if (!suggestions || suggestions.length === 0) return null;

  return (
    <div className="entity-type-suggestions">
      <p className="field-note">
        {suggestions.length} new entity type
        {suggestions.length === 1 ? "" : "s"} suggested
      </p>
      <ul className="suggestion-list">
        {suggestions.map((s) => (
          <li key={s.label} className="suggestion-item">
            <div className="suggestion-head">
              <span className="suggestion-label">{s.label}</span>
              <span className="field-note">
                {s.example_entity_names.slice(0, 3).join(", ")}
                {s.example_entity_names.length > 3 ? ", …" : ""}
              </span>
            </div>
            <div className="suggestion-actions">
              <Button
                size="sm"
                variant="primary"
                disabled={confirm.isPending}
                onClick={() => confirm.mutate(s.label)}
              >
                Add type
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={reject.isPending}
                onClick={() => reject.mutate(s.label)}
              >
                Dismiss
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
