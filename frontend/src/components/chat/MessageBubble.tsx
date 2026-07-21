import React from 'react';
import { User, Cpu } from 'lucide-react';
import { Message } from '../../lib/types';
import { MarkdownRenderer } from '../markdown/MarkdownRenderer';

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

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
        className={`flex flex-col gap-1 max-w-[85%] ${
          isUser
            ? 'bg-indigo-600 text-white rounded-2xl rounded-tr-none px-4 py-3 shadow-lg shadow-indigo-600/10'
            : 'glass-panel rounded-2xl rounded-tl-none px-5 py-4 text-gray-200'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="text-sm">
            <MarkdownRenderer content={message.content} />
          </div>
        )}
      </div>
    </div>
  );
};
