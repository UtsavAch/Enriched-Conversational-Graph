import { useState } from 'react';
import { useConversations } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';
import { Button } from '@/components/Button';
import { NewConversationDialog } from './NewConversationDialog';
import { DeleteConversationDialog } from './DeleteConversationDialog';
import './ConversationPicker.css';

export function ConversationPicker() {
  const { data: conversations, isLoading } = useConversations();
  const conversationId = useUiStore((s) => s.conversationId);
  const setConversation = useUiStore((s) => s.setConversation);
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const current = conversations?.find((c) => c.conversation_id === conversationId) ?? null;

  return (
    <div className="conv-picker">
      <label className="conv-picker-label" htmlFor="conv-select">Conversation</label>
      <select
        id="conv-select"
        className="conv-select"
        value={conversationId ?? ''}
        onChange={(e) => setConversation(e.target.value || null)}
        disabled={isLoading}
      >
        <option value="">{isLoading ? 'Loading…' : 'Select a conversation'}</option>
        {conversations?.map((c) => (
          <option key={c.conversation_id} value={c.conversation_id}>
            {c.title ? `${c.title} — ${c.conversation_id}` : c.conversation_id}
            {` (${c.n_turns} turns)`}
          </option>
        ))}
      </select>

      <Button size="sm" onClick={() => setNewDialogOpen(true)}>New</Button>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setDeleteOpen(true)}
        disabled={!conversationId}
      >
        Delete
      </Button>

      <NewConversationDialog open={newDialogOpen} onClose={() => setNewDialogOpen(false)} />
      <DeleteConversationDialog
        conversation={deleteOpen ? current : null}
        onClose={() => setDeleteOpen(false)}
        onDeleted={() => {
          setDeleteOpen(false);
          // The deleted conversation can no longer be the active one.
          setConversation(null);
        }}
      />
    </div>
  );
}
