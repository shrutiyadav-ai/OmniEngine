import React from 'react';
import { Sparkles, Wrench } from 'lucide-react';

interface ThinkingIndicatorProps {
  status: string | null;
  activeTool?: string | null;
}

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({ status, activeTool }) => {
  if (!status) return null;

  return (
    <div className="flex items-center gap-3 py-2 px-4 glass-panel rounded-xl text-xs text-indigo-300 w-fit animate-pulse-subtle">
      {activeTool ? (
        <Wrench className="w-4 h-4 text-amber-400 animate-spin" />
      ) : (
        <Sparkles className="w-4 h-4 text-indigo-400 animate-spin" />
      )}
      <span>{status}</span>
    </div>
  );
};
