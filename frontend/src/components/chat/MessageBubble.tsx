import React from 'react';
import { User, Cpu, FileText, Image as ImageIcon, RotateCcw } from 'lucide-react';
import { Message } from '../../lib/types';
import { MarkdownRenderer } from '../markdown/MarkdownRenderer';

interface MessageBubbleProps {
  message: Message;
  onRetry?: () => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onRetry }) => {
  const isUser = message.role === 'user';
  const isError = message.content.includes('*Error:') || message.content.includes('Error during execution');

  const attachments = message.attachments || [];

  return (
    <div className={`flex gap-4 p-4 max-w-4xl mx-auto ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-md ${
          isUser
            ? 'bg-gradient-to-tr from-purple-600 to-indigo-600 text-white'
            : 'bg-gradient-to-tr from-indigo-600 to-blue-600 text-white'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Cpu className="w-4 h-4" />}
      </div>

      {/* Bubble Content */}
      <div
        className={`flex flex-col gap-2 max-w-[85%] ${
          isUser
            ? 'bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 shadow-lg shadow-indigo-600/10'
            : 'glass-panel rounded-2xl rounded-tl-none px-5 py-4 text-gray-200'
        }`}
      >
        {/* Render Attachments Badge */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pb-1">
            {attachments.map((att: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 bg-black/30 border border-white/20 rounded-lg px-2.5 py-1 text-xs"
              >
                {att.type === 'image' ? (
                  <ImageIcon className="w-3.5 h-3.5 text-blue-300" />
                ) : (
                  <FileText className="w-3.5 h-3.5 text-indigo-300" />
                )}
                <span className="truncate max-w-[160px] font-medium">{att.filename || 'Attachment'}</span>
              </div>
            ))}
          </div>
        )}

        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="text-sm">
            <MarkdownRenderer content={message.content} />
          </div>
        )}

        {/* Retry Button on Error */}
        {isError && onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 bg-red-950/40 border border-red-800/60 rounded-lg px-3 py-1.5 transition-colors self-start"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Retry request</span>
          </button>
        )}
      </div>
    </div>
  );
};
