import React, { useState } from 'react';
import { api } from '../api';
import { Database, Upload, AlertCircle, CheckCircle, FileImage } from 'lucide-react';

export default function DatabaseRegistry() {
  const [name, setName] = useState('');
  const [category, setCategory] = useState('criminal');
  const [personId, setPersonId] = useState('');
  const [file, setFile] = useState(null);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successInfo, setSuccessInfo] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name || !file) return;

    setLoading(true);
    setError('');
    setSuccessInfo(null);

    try {
      const data = await api.addPerson(name, category, file, personId);
      setSuccessInfo(data);
      setName('');
      setPersonId('');
      setFile(null);
      // Reset file input element if needed
      document.getElementById('ref-file-input').value = '';
    } catch (err) {
      setError(err.message || 'Failed to add person/reference to database');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '650px', margin: '0 auto', width: '100%' }}>
      <div className="page-header" style={{ justifyContent: 'center', border: 'none', padding: '0', marginBottom: '1.5rem' }}>
        <div style={{ textAlign: 'center' }}>
          <h1 className="page-title">Suspect & Missing Registry</h1>
          <p className="page-desc">Admin Portal: Register new individuals or insert secondary reference vectors to existing clusters.</p>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">
          <Database size={20} style={{ color: 'var(--primary)' }} />
          <span>Register Person Profile</span>
        </h2>

        {successInfo && (
          <div style={{ 
            backgroundColor: 'rgba(16, 185, 129, 0.08)', 
            border: '1px solid var(--status-success)', 
            borderRadius: '8px', 
            padding: '1.25rem', 
            marginBottom: '1.5rem',
            color: '#d1fae5',
            fontSize: '0.85rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--status-success)', fontWeight: '600' }}>
              <CheckCircle size={18} />
              <span>Reference Successfully Indexed</span>
            </div>
            <p>Indexed Identity: <strong style={{ color: '#fff' }}>{successInfo.name}</strong></p>
            <p>Assigned Person ID: <code style={{ color: 'var(--primary)' }}>{successInfo.person_id}</code></p>
            <p style={{ marginTop: '0.5rem', color: '#94a3b8' }}>
              Status: Reference vector #{successInfo.reference_count_for_person} added to database.<br />
              Database stats: {successInfo.total_people_in_database} unique profiles, {successInfo.total_reference_images} total vectors.
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Full Identity / Name</label>
            <input
              type="text"
              id="name"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., John Doe"
              disabled={loading}
            />
          </div>

          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="category">Registry classification</label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={loading}
              >
                <option value="criminal">Criminal Suspect List</option>
                <option value="missing_person">Missing Persons Register</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="person-id">Person ID (Optional)</label>
              <input
                type="text"
                id="person-id"
                value={personId}
                onChange={(e) => setPersonId(e.target.value)}
                placeholder="Leave blank for new person"
                disabled={loading}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginTop: '0.5rem' }}>
            <label>Reference Portrait Photograph</label>
            <div className="upload-dropzone" style={{ padding: '2rem 1rem' }}>
              <input
                type="file"
                id="ref-file-input"
                required
                accept="image/*"
                onChange={(e) => setFile(e.target.files[0])}
                disabled={loading}
              />
              <label htmlFor="ref-file-input" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                <FileImage size={28} style={{ color: file ? 'var(--status-success)' : '#64748b' }} />
                <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                  {file ? file.name : 'Select reference image file'}
                </span>
              </label>
            </div>
          </div>

          <button 
            type="submit" 
            className="btn-primary" 
            style={{ width: '100%', marginTop: '1rem' }}
            disabled={loading || !name || !file}
          >
            {loading ? 'Compiling Face Vector...' : 'Write Reference to FAISS Index'}
          </button>
        </form>

        {error && (
          <div className="error-banner" style={{ marginTop: '1rem' }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}
