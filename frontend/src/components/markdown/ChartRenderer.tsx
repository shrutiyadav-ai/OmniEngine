import React from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

interface ChartRendererProps {
  jsonConfig: string;
}

const COLORS = ['#6366f1', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', '#3b82f6'];

export const ChartRenderer: React.FC<ChartRendererProps> = ({ jsonConfig }) => {
  try {
    const config = JSON.parse(jsonConfig);
    const { type = 'bar', data = [], xKey = 'name', yKey = 'value' } = config;

    return (
      <div className="my-4 p-4 rounded-xl glass-panel border border-gray-800 h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {type === 'line' ? (
            <LineChart data={data}>
              <XAxis dataKey={xKey} stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151' }} />
              <Line type="monotone" dataKey={yKey} stroke="#6366f1" strokeWidth={2} />
            </LineChart>
          ) : type === 'pie' ? (
            <PieChart>
              <Pie data={data} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={80} fill="#8884d8" label>
                {data.map((_: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151' }} />
            </PieChart>
          ) : (
            <BarChart data={data}>
              <XAxis dataKey={xKey} stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip contentStyle={{ backgroundColor: '#111827', borderColor: '#374151' }} />
              <Bar dataKey={yKey} fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    );
  } catch (e) {
    return <div className="p-3 bg-red-950/40 text-red-400 text-xs rounded-lg">Failed to render chart: invalid JSON config</div>;
  }
};
