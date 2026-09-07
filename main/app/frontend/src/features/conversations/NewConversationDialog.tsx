import { useState } from 'react';
import { useHealth, useSendTurn } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';
import { Button } from '@/components/Button';
import { Dialog } from '@/components/Dialog';

/**
 * Create a conversation.
 *
 * There is no dedicated "create conversation" endpoint — the chat endpoint
 * creates one on first turn. That is a deliberate backend choice (an empty
 * conversation has no research value), so this dialog explains the CLI route
 * when live chat is disabled rather than offering an action that cannot work.
 */
export function NewConversationDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: health } = useHealth();
  const setConversation = useUiStore((s) => s.setConversation);
  const sendTurn = useSendTurn();

  const [id, setId] = useState('');
  const [firstMessage, setFirstMessage] = useState('');

  const chatEnabled = health?.chat_enabled ?? false;
  const cleanId = id.trim().replace(/\s+/g, '_');
  const canCreate = chatEnabled && cleanId.length > 0 && firstMessage.trim().length > 0;

  const handleCreate = async () => {
    if (!canCreate) return;
    await sendTurn.mutateAsync({ conversationId: cleanId, question: firstMessage.trim() });
    setConversation(cleanId);
    setId(''); setFirstMessage('');
    onClose();
  };

  return (
    <Dialog
      open={open}
      title="New conversation"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={handleCreate} disabled={!canCreate || sendTurn.isPending}>
            {sendTurn.isPending ? 'Creating…' : 'Create'}
          </Button>
        </>
      }
    >
      {!chatEnabled ? (
        <p className="field-hint" style={{ lineHeight: 1.65 }}>
          Creating a conversation from the app needs live chat, which is off on this server.
          <br /><br />
          Start the server with <code>GM_ENABLE_CHAT=1</code> to enable it, or build a graph
          from a transcript instead:
          <br />
          <code style={{ display: 'block', marginTop: 6, fontSize: 'var(--text-xs)' }}>
            python -m scripts.ingest_conversation transcript.json --conversation-id my_id
          </code>
        </p>
      ) : (
        <>
          <div className="field-group">
            <label htmlFor="new-conv-id">Conversation ID</label>
            <input
              id="new-conv-id" value={id} autoComplete="off"
              onChange={(e) => setId(e.target.value)}
              placeholder="phase3_planning"
            />
            <span className="field-hint">Used in file paths and URLs. Spaces become underscores.</span>
          </div>

          <div className="field-group">
            <label htmlFor="new-conv-msg">First message</label>
            <input
              id="new-conv-msg" value={firstMessage}
              onChange={(e) => setFirstMessage(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && canCreate) handleCreate(); }}
              placeholder="What should we work on?"
            />
          </div>

          {sendTurn.isError && (
            <p className="field-hint" style={{ color: 'var(--c-constraint)' }}>
              {(sendTurn.error as Error).message}
            </p>
          )}
        </>
      )}
    </Dialog>
  );
}
