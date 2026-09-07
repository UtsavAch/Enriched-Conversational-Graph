import { useState } from 'react';
import { useConversations } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';
import { Button } from '@/components/Button';
import { NewConversationDialog } from './NewConversationDialog';
import './ConversationPicker.css';

export function ConversationPicker() {
  const { data: conversations, isLoading } = useConversations();
  const conversationId = useUiStore((s) => s.conversationId);
  const setConversation = useUiStore((s) => s.setConversation);
  const [dialogOpen, setDialogOpen] = useState(false);

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

      <Button size="sm" onClick={() => setDialogOpen(true)}>New</Button>

      <NewConversationDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  );
}
