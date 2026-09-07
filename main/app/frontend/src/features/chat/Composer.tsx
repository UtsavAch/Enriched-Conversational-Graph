import { useEffect, useRef, useState } from 'react';
import { useHealth, useSendTurn } from '@/api/queries';
import { useUiStore } from '@/store/uiStore';

/**
 * Message input.
 *
 * Three distinct disabled reasons, each with its own message. A single greyed
 * box that does not say why is the thing that makes people file bugs.
 */
export function Composer() {
  const { data: health } = useHealth();
  const conversationId = useUiStore((s) => s.conversationId);
  const selectNode = useUiStore((s) => s.selectNode);
  const sendTurn = useSendTurn();
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const chatEnabled = health?.chat_enabled ?? false;
  const busy = sendTurn.isPending;
  const disabled = !conversationId || !chatEnabled || busy;

  const placeholder = !conversationId ? 'Select a conversation first'
    : !chatEnabled ? 'Live chat is disabled on this server'
    : busy ? 'Working…'
    : 'Ask something…';

  const note = !chatEnabled && conversationId
    ? 'Restart the server with GM_ENABLE_CHAT=1 to send messages.'
    : null;

  // Grow with content, up to a ceiling.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 140)}px`;
  }, [value]);

  const submit = async () => {
    const question = value.trim();
    if (!question || disabled || !conversationId) return;
    setValue('');
    try {
      const result = await sendTurn.mutateAsync({ conversationId, question });
      // Select the new node so the graph and inspector jump straight to it.
      if (result.turn?.node_id) selectNode(result.turn.node_id);
    } catch {
      // Restore the text so a failed send does not lose what was typed.
      setValue(question);
    }
  };

  return (
    <div className="composer-wrap">
      <div className="composer">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit(); }
          }}
          aria-label="Message"
        />
        <button
          className="composer-send"
          onClick={() => void submit()}
          disabled={disabled || !value.trim()}
          aria-label="Send message"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden>
            <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor" />
          </svg>
        </button>
      </div>

      {note && <p className="composer-note">{note}</p>}
      {sendTurn.isError && (
        <p className="composer-note composer-error">{(sendTurn.error as Error).message}</p>
      )}
    </div>
  );
}
