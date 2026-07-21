import { Session, Message, StreamEvent } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key-change-me-in-production';

export async function fetchSessions(): Promise<Session[]> {
  const res = await fetch(`${API_BASE}/api/v1/sessions`, {
    headers: {
      'X-API-Key': API_KEY,
    },
  });
  if (!res.ok) throw new Error('Failed to fetch sessions');
  const data = await res.json();
  return data.sessions || [];
}

export async function createSession(title: string = 'New Chat'): Promise<Session> {
  const res = await fetch(`${API_BASE}/api/v1/sessions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error('Failed to create session');
  return res.json();
}

export async function fetchSessionDetail(sessionId: string): Promise<{ session: Session; messages: Message[] }> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, {
    headers: {
      'X-API-Key': API_KEY,
    },
  });
  if (!res.ok) throw new Error('Failed to fetch session detail');
  const data = await res.json();
  return {
    session: data,
    messages: data.messages || [],
  };
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: {
      'X-API-Key': API_KEY,
    },
  });
  if (!res.ok) throw new Error('Failed to delete session');
}

export async function* streamChat(
  message: string,
  sessionId?: string,
  modelPreference?: string,
  attachments: any[] = []
): AsyncGenerator<StreamEvent, void, unknown> {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      model_preference: modelPreference,
      attachments,
      stream: true,
    }),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Chat request failed: ${errorText}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error('ReadableStream not supported');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const jsonStr = line.replace('data: ', '').trim();
          if (jsonStr) {
            const parsed: StreamEvent = JSON.parse(jsonStr);
            yield parsed;
          }
        } catch (e) {
          console.warn('Failed to parse SSE payload:', line, e);
        }
      }
    }
  }
}
