import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';
import { ChartRenderer } from './ChartRenderer';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const language = match ? match[1] : '';
          const value = String(children).replace(/\n$/, '');

          if (!inline && language === 'chart') {
            return <ChartRenderer jsonConfig={value} />;
          }

          if (!inline && match) {
            return <CodeBlock language={language} value={value} />;
          }

          return (
            <code className="bg-gray-800 text-indigo-300 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
              {children}
            </code>
          );
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-4 border border-gray-800 rounded-xl">
              <table className="min-w-full divide-y divide-gray-800 text-sm">{children}</table>
            </div>
          );
        },
        th({ children }) {
          return <th className="px-4 py-2 bg-gray-900 text-left text-xs font-semibold text-gray-300 uppercase">{children}</th>;
        },
        td({ children }) {
          return <td className="px-4 py-2 border-t border-gray-800/50 text-gray-300">{children}</td>;
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
};
