import React from 'react';
import { useSessions, useChat } from '../../lib/hooks';
import { Sidebar } from './Sidebar';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export const ChatContainer: React.FC = () => {
  const {
    sessions,
    activeSessionId,
    setActiveSessionId,
    createSession,
    deleteSession,
  } = useSessions();

  const {
    messages,
    isStreaming,
    thinkingStatus,
    activeTool,
    sendMessage,
  } = useChat(activeSessionId);

  const handleSendMessage = async (text: string, modelPreference?: string, attachments?: any[]) => {
    let currentSessionId = activeSessionId;
    if (!currentSessionId) {
      currentSessionId = await createSession();
    }

    if (currentSessionId) {
      sendMessage(text, modelPreference, attachments);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={setActiveSessionId}
        onCreateSession={createSession}
        onDeleteSession={deleteSession}
      />
      <main className="flex-1 flex flex-col h-full overflow-hidden">
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          thinkingStatus={thinkingStatus}
          activeTool={activeTool}
        />
        <ChatInput onSendMessage={handleSendMessage} disabled={isStreaming} />
      </main>
    </div>
  );
};
