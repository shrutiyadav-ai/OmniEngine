import React, { useRef, useEffect } from 'react';
import { Message } from '../../lib/types';
import { MessageBubble } from './MessageBubble';
import { ThinkingIndicator } from '../ui/ThinkingIndicator';

interface MessageListProps {
  messages: Message[];
  isStreaming?: boolean;
  thinkingStatus?: string | null;
  activeTool?: string | null;
  onRetry?: () => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isStreaming,
  thinkingStatus,
  activeTool,
  onRetry,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, thinkingStatus]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center p-8 text-gray-500">
          <div className="p-4 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 mb-4">
            <h2 className="text-xl font-bold text-white mb-2">Welcome to OmniEngine</h2>
            <p className="text-sm text-gray-400 max-w-md">
              Tier-1 multi-model AI assistant powered by LangGraph, dynamic routing, document intelligence, and vector memory.
            </p>
          </div>
        </div>
      ) : (
        messages.map((message) => (
          <MessageBubble key={message.id} message={message} onRetry={onRetry} />
        ))
      )}

      {isStreaming && (
        <div className="max-w-4xl mx-auto px-4">
          <ThinkingIndicator status={thinkingStatus || 'Generating response...'} activeTool={activeTool} />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
