import { useState, useCallback, useEffect } from 'react';
import { Message, Session } from './types';
import { fetchSessions, createSession, fetchSessionDetail, deleteSession, streamChat } from './api';

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadSessions = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchSessions();
      setSessions(data);
      if (data.length > 0 && !activeSessionId) {
        setActiveSessionId(data[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [activeSessionId]);

  useEffect(() => {
    loadSessions();
  }, []);

  const handleCreateSession = async () => {
    try {
      const newSession = await createSession('New Chat');
      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newSession.id);
      return newSession.id;
    } catch (e) {
      console.error(e);
      return null;
    }
  };

  const handleDeleteSession = async (id: string) => {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        const remaining = sessions.filter((s) => s.id !== id);
        setActiveSessionId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (e) {
      console.error(e);
    }
  };

  return {
    sessions,
    activeSessionId,
    setActiveSessionId,
    loading,
    createSession: handleCreateSession,
    deleteSession: handleDeleteSession,
    reloadSessions: loadSessions,
  };
}

export function useChat(sessionId: string | null) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setMessages([]);
      return;
    }

    fetchSessionDetail(sessionId)
      .then((data) => setMessages(data.messages))
      .catch(console.error);
  }, [sessionId]);

  const sendMessage = async (text: string, modelPreference?: string, attachments: any[] = []) => {
    if (!text.trim() || isStreaming) return;

    const userMessage: Message = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: text,
      sequence_number: messages.length + 1,
      attachments,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);
    setThinkingStatus('Initializing...');

    const assistantMsgId = `ast_${Date.now()}`;
    let assistantText = '';

    try {
      for await (const event of streamChat(text, sessionId || undefined, modelPreference, attachments)) {
        if (event.event === 'thinking') {
          setThinkingStatus(event.data);
        } else if (event.event === 'tool_start') {
          setActiveTool(event.metadata?.tool_name || 'tool');
          setThinkingStatus(`Using ${event.metadata?.tool_name || 'tool'}...`);
        } else if (event.event === 'tool_result') {
          setActiveTool(null);
        } else if (event.event === 'token') {
          assistantText += event.data;
          setMessages((prev) => {
            const existingIdx = prev.findIndex((m) => m.id === assistantMsgId);
            const updatedMsg: Message = {
              id: assistantMsgId,
              role: 'assistant',
              content: assistantText,
              sequence_number: prev.length + 1,
              created_at: new Date().toISOString(),
            };

            if (existingIdx >= 0) {
              const clone = [...prev];
              clone[existingIdx] = updatedMsg;
              return clone;
            } else {
              return [...prev, updatedMsg];
            }
          });
        } else if (event.event === 'done') {
          break;
        }
      }
    } catch (e: any) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: `err_${Date.now()}`,
          role: 'assistant',
          content: `*Error: ${e.message || 'Stream disconnected'}*`,
          sequence_number: prev.length + 1,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsStreaming(false);
      setThinkingStatus(null);
      setActiveTool(null);
    }
  };

  const retryLastMessage = async () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMsg) {
      // Remove any trailing error message
      setMessages((prev) => prev.filter((m) => !m.content.includes('*Error:')));
      await sendMessage(lastUserMsg.content, undefined, lastUserMsg.attachments);
    }
  };

  return {
    messages,
    isStreaming,
    thinkingStatus,
    activeTool,
    sendMessage,
    retryLastMessage,
  };
}
