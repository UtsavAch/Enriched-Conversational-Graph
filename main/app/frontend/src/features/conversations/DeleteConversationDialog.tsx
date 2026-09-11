import { ApiError } from '@/api/client';
import { useDeleteConversation } from '@/api/queries';
import { Button } from '@/components/Button';
import { Dialog } from '@/components/Dialog';
import type { ConversationSummary } from '@/types/api';

interface Props {
  /** The conversation to confirm deletion for. `null` keeps the dialog closed. */
  conversation: ConversationSummary | null;
  onClose: () => void;
  onDeleted: () => void;
}

/**
 * Confirms before deleting a conversation. Deletion is total and
 * irreversible: the backend removes the whole conversation directory in one
 * go — every interaction, entity, and state node, plus its documents folder
 * (including any archived raw files) — not just the visible transcript. The
 * global document corpus and other conversations are untouched.
 */
export function DeleteConversationDialog({ conversation, onClose, onDeleted }: Props) {
  const del = useDeleteConversation();

  const handleDelete = async () => {
    if (!conversation) return;
    await del.mutateAsync(conversation.conversation_id);
    onDeleted();
  };

  return (
    <Dialog
      open={Boolean(conversation)}
      title="Delete conversation"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={handleDelete} disabled={del.isPending}>
            {del.isPending ? 'Deleting…' : 'Delete permanently'}
          </Button>
        </>
      }
    >
      {conversation && (
        <p className="field-hint" style={{ lineHeight: 1.65 }}>
          This permanently deletes{' '}
          <strong>{conversation.title || conversation.conversation_id}</strong>
          {' '}(<code>{conversation.conversation_id}</code>) — {conversation.n_turns}{' '}
          turn{conversation.n_turns === 1 ? '' : 's'}, {conversation.n_entities}{' '}
          entit{conversation.n_entities === 1 ? 'y' : 'ies'}, {conversation.n_state_nodes}{' '}
          state node{conversation.n_state_nodes === 1 ? '' : 's'}, and any documents
          archived for it. This cannot be undone.
        </p>
      )}

      {del.isError && (
        <p className="field-hint" style={{ color: 'var(--c-constraint)' }}>
          {(del.error as ApiError).detail || (del.error as Error).message}
        </p>
      )}
    </Dialog>
  );
}
