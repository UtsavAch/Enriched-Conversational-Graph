import { useState } from 'react';
import { ApiError } from '@/api/client';
import { useCreateConversation, useHealth } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';
import { Button } from '@/components/Button';
import { Dialog } from '@/components/Dialog';

/**
 * Turn a topic into a slug preview, purely for the "will be saved as" hint.
 * Mirrors the backend's `_slugify` closely enough to be a useful preview —
 * the server has final say (and appends `_2`, `_3`, ... on collision), so
 * this never needs to be authoritative, just close.
 */
function previewId(topic: string): string {
  const slug = topic.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  return (slug || 'conversation').slice(0, 40);
}

/**
 * Create a conversation.
 *
 * Topic only — no id to invent, no first message. The backend slugifies the
 * topic into a unique id (see `_unique_conversation_id`); creation and
 * chatting are deliberately separate steps, so send the first message from
 * the composer once the conversation exists, not here. That gap is what
 * makes document selection (the Documents panel) meaningful for a turn that
 * hasn't happened yet — scope documents first, then the *first* message is
 * already retrieval-scoped instead of silently defaulting to the entire
 * global document corpus.
 *
 * Creation itself needs no LLM call, so it works even with live chat
 * disabled; only sending messages afterward needs GM_ENABLE_CHAT=1, which the
 * composer already explains on its own.
 */
export function NewConversationDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: health } = useHealth();
  const setConversation = useUiStore((s) => s.setConversation);
  const create = useCreateConversation();

  const [topic, setTopic] = useState('');

  const chatEnabled = health?.chat_enabled ?? false;
  const cleanTopic = topic.trim();
  const canCreate = cleanTopic.length > 0;

  const handleCreate = async () => {
    if (!canCreate) return;
    const result = await create.mutateAsync(cleanTopic);
    setConversation(result.conversation_id);
    setTopic('');
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
          <Button variant="primary" onClick={handleCreate} disabled={!canCreate || create.isPending}>
            {create.isPending ? 'Creating…' : 'Create'}
          </Button>
        </>
      }
    >
      <div className="field-group">
        <label htmlFor="new-conv-topic">Topic</label>
        <input
          id="new-conv-topic" value={topic} autoComplete="off"
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && canCreate) handleCreate(); }}
          placeholder="What this conversation is about"
        />
        <span className="field-hint">
          {cleanTopic ? <>Saved as <code>{previewId(cleanTopic)}</code> (a number is appended if that id is already taken).</>
            : 'The conversation id is generated from this — no need to invent one.'}
        </span>
      </div>

      {!chatEnabled && (
        <p className="field-hint" style={{ lineHeight: 1.65 }}>
          Live chat is off on this server — you can create the conversation and
          select its documents now, but sending messages needs the server
          restarted with <code>GM_ENABLE_CHAT=1</code>.
        </p>
      )}

      {create.isError && (
        <p className="field-hint" style={{ color: 'var(--c-constraint)' }}>
          {(create.error as ApiError).detail || (create.error as Error).message}
        </p>
      )}
    </Dialog>
  );
}
