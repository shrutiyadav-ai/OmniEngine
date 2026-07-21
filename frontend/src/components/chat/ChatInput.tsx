import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Sparkles } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (text: string, modelPreference?: string, attachments?: any[]) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, disabled }) => {
  const [input, setInput] = useState('');
  const [modelPreference, setModelPreference] = useState<string>('gpt-4o');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    if (!input.trim() || disabled) return;
    onSendMessage(input, modelPreference);
    setInput('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [input]);

  return (
    <div className="p-4 bg-background border-t border-gray-800">
      <div className="max-w-4xl mx-auto glass-input rounded-2xl p-2 flex flex-col gap-2 shadow-xl">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask OmniEngine anything..."
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent border-0 text-white placeholder-gray-500 focus:outline-none focus:ring-0 px-3 py-1.5 resize-none text-sm min-h-[40px] max-h-[160px]"
        />

        <div className="flex items-center justify-between px-2 pt-1 border-t border-gray-800/40 text-xs">
          {/* Model Preference Dropdown */}
          <div className="flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <select
              value={modelPreference}
              onChange={(e) => setModelPreference(e.target.value)}
              className="bg-gray-900 text-gray-300 border border-gray-800 rounded-lg px-2 py-1 focus:outline-none focus:border-indigo-500 text-xs"
            >
              <option value="gpt-4o">Auto (GPT-4o)</option>
              <option value="claude-sonnet-4-20250514">Claude 3.5 Sonnet</option>
              <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
              <option value="o1">OpenAI o1 Reasoning</option>
            </select>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="p-1.5 text-gray-400 hover:text-gray-200 transition-colors rounded-lg hover:bg-gray-800"
              title="Attach File/Image"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <button
              onClick={handleSend}
              disabled={!input.trim() || disabled}
              className={`p-2 rounded-xl flex items-center justify-center transition-all ${
                input.trim() && !disabled
                  ? 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-md shadow-indigo-600/30'
                  : 'bg-gray-800 text-gray-600 cursor-not-allowed'
              }`}
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
