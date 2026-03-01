import React, { useState, useEffect } from 'react';

const API_TOKEN = import.meta.env.VITE_API_TOKEN || "v2x-secret-token-change-in-prod";
const API_URL = `http://${window.location.hostname}:8000`;

export default function HistoryTable() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_URL}/api/history`, {
      headers: { Authorization: `Bearer ${API_TOKEN}` },
    })
      .then((res) => res.json())
      .then((data) => {
        setHistory(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const formatTimestamp = (ts) => {
    if (!ts) return '—';
    try {
      const d = new Date(ts);
      return d.toLocaleString('ro-RO', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch { return ts; }
  };

  const scoreColor = (score) => {
    if (score >= 75) return 'text-green-400';
    if (score >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-3 text-neutral-500 text-xs font-mono">
        Loading history…
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="flex items-center justify-center py-3 text-neutral-500 text-xs font-mono">
        No history available
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-neutral-400">Session History</span>
        <span className="text-[10px] text-neutral-600 font-mono">Last {history.length}</span>
      </div>
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-neutral-500 border-b border-white/5">
            <th className="text-left py-1.5 pr-3 font-medium">Time</th>
            <th className="text-right py-1.5 px-2 font-medium">Dur.</th>
            <th className="text-right py-1.5 px-2 font-medium">Prevented</th>
            <th className="text-right py-1.5 pl-2 font-medium">Score</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr key={row.id} className="border-b border-white/[0.03] hover:bg-white/[0.03] transition-colors">
              <td className="py-1.5 pr-3 text-neutral-400">{formatTimestamp(row.timestamp)}</td>
              <td className="py-1.5 px-2 text-right text-neutral-300">{row.duration}s</td>
              <td className="py-1.5 px-2 text-right text-neutral-300">{row.collisions_prevented}</td>
              <td className={`py-1.5 pl-2 text-right font-bold ${scoreColor(row.cooperation_score)}`}>
                {row.cooperation_score}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
