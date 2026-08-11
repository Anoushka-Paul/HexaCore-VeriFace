import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { History, Search, RefreshCw } from 'lucide-react';

export default function AuditTrail() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [error, setError] = useState('');

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getAudit();
      setLogs(data);
    } catch (err) {
      setError(err.message || 'Failed to fetch search audit trail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter(log => {
    const term = searchTerm.toLowerCase();
    return (
      (log.filename && log.filename.toLowerCase().includes(term)) ||
      (log.top_match_name && log.top_match_name.toLowerCase().includes(term)) ||
      (log.top_match_person_id && log.top_match_person_id.toLowerCase().includes(term)) ||
      (log.confidence && log.confidence.toLowerCase().includes(term))
    );
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Search Query Audit trail</h1>
          <p className="page-desc">Review logs of all face queries made across standard and sketch-to-photo pipeline operations.</p>
        </div>
        <button className="btn-primary" onClick={fetchLogs} disabled={loading} style={{ padding: '0.5rem 1rem', fontSize: '0.85rem' }}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Records</span>
        </button>
      </div>

      <div className="card">
        {/* Search Bar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem', maxWidth: '350px', background: 'var(--bg-main)', border: '1px solid var(--border-color)', padding: '0.5rem 1rem', borderRadius: '8px' }}>
          <Search size={16} style={{ color: '#64748b' }} />
          <input
            type="text"
            placeholder="Search by file, name, id, status..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ border: 'none', background: 'transparent', padding: '0', fontSize: '0.85rem', width: '100%' }}
          />
        </div>

        {error && (
          <div className="error-banner">
            <span>{error}</span>
          </div>
        )}

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Query Timestamp</th>
                <th>Source Filename</th>
                <th>Top Candidate ID</th>
                <th>Indexed Name</th>
                <th>Similarity Index</th>
                <th>Confidence Threshold</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length > 0 ? (
                filteredLogs.map((log) => {
                  const localTime = log.timestamp 
                    ? new Date(log.timestamp).toLocaleString()
                    : 'N/A';
                  return (
                    <tr key={log.id}>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#94a3b8' }}>
                        {localTime}
                      </td>
                      <td style={{ fontWeight: '500' }}>
                        {log.filename}
                      </td>
                      <td style={{ fontFamily: 'monospace', color: 'var(--primary)' }}>
                        {log.top_match_person_id || '—'}
                      </td>
                      <td style={{ color: log.top_match_name ? '#fff' : '#64748b' }}>
                        {log.top_match_name || 'No Face Found'}
                      </td>
                      <td style={{ fontWeight: '600' }}>
                        {log.similarity !== null && log.similarity !== undefined 
                          ? `${(log.similarity * 100).toFixed(1)}%` 
                          : '—'}
                      </td>
                      <td>
                        {log.confidence ? (
                          <span className={`badge ${log.confidence.includes('likely') ? 'badge-critical' : log.confidence.includes('possible') ? 'badge-warning' : 'badge-neutral'}`}>
                            {log.confidence}
                          </span>
                        ) : (
                          <span className="badge badge-neutral">No Match</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                    {loading ? 'Retrieving historical logs...' : 'No audit records matching query parameters found.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
