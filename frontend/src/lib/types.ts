export type Role = 'user' | 'assistant' | 'system' | 'tool';

export interface Attachment {
  type: 'image' | 'file' | 'url';
  url?: string;
  content?: string;
  filename?: string;
  mime_type?: string;
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  sequence_number: number;
  token_count?: number;
  model_used?: string;
  cost_usd?: number;
  latency_ms?: number;
  tool_calls?: Record<string, any>;
  tool_results?: Record<string, any>;
  attachments?: Attachment[];
  confidence_score?: number;
  created_at: string;
}

export interface Session {
  id: string;
  title: string;
  is_active: boolean;
  model_preference?: string;
  total_tokens: number;
  total_cost_usd: number;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export type StreamEventType =
  | 'token'
  | 'tool_start'
  | 'tool_result'
  | 'thinking'
  | 'error'
  | 'done'
  | 'metadata'
  | 'cost_warning';

export interface StreamEvent {
  event: StreamEventType;
  data: string;
  metadata?: Record<string, any>;
}
