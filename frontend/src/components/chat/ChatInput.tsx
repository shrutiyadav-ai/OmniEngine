import React, { useState, useRef, useEffect } from 'react';
import { Send, Paperclip, Sparkles, X, FileText, Image as ImageIcon } from 'lucide-react';

interface AttachmentItem {
  filename: string;
  type: 'file' | 'image' | 'url';
  mime_type: string;
  content?: string;
  url?: string;
  size?: number;
}

interface ChatInputProps {
  onSendMessage: (text: string, modelPreference?: string, attachments?: AttachmentItem[]) => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, disabled }) => {
  const [input, setInput] = useState('');
  const [modelPreference, setModelPreference] = useState<string>('gpt-4o');
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if ((!input.trim() && attachments.length === 0) || disabled) return;
    const sendText = input.trim() || (attachments.length > 0 ? `[Analyze attached document: ${attachments.map(a => a.filename).join(', ')}]` : '');
    onSendMessage(sendText, modelPreference, attachments);
    setInput('');
    setAttachments([]);
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      const isImage = file.type.startsWith('image/');
      const reader = new FileReader();

      reader.onload = (event) => {
        const result = event.target?.result as string;
        const newAttachment: AttachmentItem = {
          filename: file.name,
          type: isImage ? 'image' : 'file',
          mime_type: file.type || (isImage ? 'image/png' : 'application/octet-stream'),
          url: result,
          content: isImage ? undefined : result,
          size: file.size,
        };
        setAttachments((prev) => [...prev, newAttachment]);
      };

      if (isImage || file.name.match(/\.(pdf|docx|doc|xlsx|xls)$/i)) {
        reader.readAsDataURL(file);
      } else {
        reader.readAsText(file);
      }
    });

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
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
        {/* Attachment Previews */}
        {attachments.length > 0 && (
          <div className="flex flex-wrap gap-2 px-2 pt-1">
            {attachments.map((att, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 bg-gray-900 border border-gray-700/60 rounded-lg px-2.5 py-1 text-xs text-gray-200"
              >
                {att.type === 'image' ? (
                  <ImageIcon className="w-3.5 h-3.5 text-blue-400" />
                ) : (
                  <FileText className="w-3.5 h-3.5 text-indigo-400" />
                )}
                <span className="max-w-[150px] truncate">{att.filename}</span>
                <button
                  type="button"
                  onClick={() => removeAttachment(idx)}
                  className="text-gray-400 hover:text-red-400 ml-1"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask OmniEngine anything or upload files..."
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

          {/* Action Buttons & Hidden File Input */}
          <div className="flex items-center gap-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept=".pdf,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg"
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="p-1.5 text-gray-400 hover:text-gray-200 transition-colors rounded-lg hover:bg-gray-800"
              title="Attach Document / Image (PDF, DOCX, TXT, CSV, XLSX, PNG, JPG)"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <button
              onClick={handleSend}
              disabled={(!input.trim() && attachments.length === 0) || disabled}
              className={`p-2 rounded-xl flex items-center justify-center transition-all ${
                (input.trim() || attachments.length > 0) && !disabled
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
