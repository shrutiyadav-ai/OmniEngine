import React from 'react';
import { Plus, MessageSquare, Trash2, Cpu } from 'lucide-react';
import { Session } from '../../lib/types';

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onCreateSession: () => void;
  onDeleteSession: (id: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
}) => {
  return (
    <aside className="w-64 glass-panel h-full flex flex-col border-r border-gray-800 p-4 select-none">
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-2 py-3 mb-4 border-b border-gray-800/80">
        <div className="p-2 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 shadow-lg shadow-indigo-500/20">
          <Cpu className="w-5 h-5 text-white" />
        </div>
        <div>
          <h1 className="font-bold text-white text-base tracking-tight">OmniEngine</h1>
          <p className="text-[10px] text-indigo-400 font-medium">Multi-Agent System</p>
        </div>
      </div>

      {/* New Chat Button */}
      <button
        onClick={onCreateSession}
        className="w-full flex items-center justify-center gap-2 py-2.5 px-4 mb-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-medium text-sm transition-all shadow-md shadow-indigo-600/20"
      >
        <Plus className="w-4 h-4" />
        <span>New Chat</span>
      </button>

      {/* Session History List */}
      <div className="flex-1 overflow-y-auto space-y-1 pr-1">
        <div className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">Recent Chats</div>
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          return (
            <div
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer text-sm transition-all ${
                isActive
                  ? 'bg-indigo-600/20 text-white border border-indigo-500/30'
                  : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'
              }`}
            >
              <div className="flex items-center gap-2.5 truncate">
                <MessageSquare className={`w-4 h-4 shrink-0 ${isActive ? 'text-indigo-400' : 'text-gray-500'}`} />
                <span className="truncate">{session.title || 'Untitled Chat'}</span>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteSession(session.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-opacity"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </aside>
  );
};
