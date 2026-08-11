import React, { useState, useRef } from 'react';
import { api } from '../api';
import { Upload, Camera, AlertCircle, FileImage, ShieldAlert } from 'lucide-react';

export default function SearchPhoto() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [category, setCategory] = useState('all');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selectedFile = e.dataTransfer.files[0];
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreview(URL.createObjectURL(selectedFile));
    }
  };

  const onButtonClick = () => {
    fileInputRef.current.click();
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setError('');
    setResults([]);

    try {
      const data = await api.searchFace(file, category);
      setResults(data);
    } catch (err) {
      setError(err.message || 'Face search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Photo Recognition search</h1>
          <p className="page-desc">Upload a high-resolution photograph to identify matching database profiles.</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Upload Column */}
        <div className="card">
          <h2 className="card-title">
            <Camera size={20} style={{ color: 'var(--primary)' }} />
            <span>Target Image Acquisition</span>
          </h2>

          <form onSubmit={handleSearch}>
            <div 
              className={`upload-dropzone ${dragActive ? 'drag-active' : ''} ${loading ? 'scanning-animation-container' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
              onClick={onButtonClick}
            >
              {loading && <div className="scanning-laser" />}
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                style={{ display: 'none' }}
                accept="image/*"
                onChange={handleChange}
                disabled={loading}
              />

              {preview ? (
                <div style={{ position: 'relative', width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                  <img 
                    src={preview} 
                    alt="Preview" 
                    style={{ maxHeight: '200px', maxWidth: '100%', objectFit: 'contain', borderRadius: '8px', border: '1px solid var(--border-color)' }} 
                  />
                  <p className="upload-text" style={{ marginTop: '0.5rem' }}>
                    Click or drag new image to replace
                  </p>
                </div>
              ) : (
                <>
                  <Upload size={36} className="upload-icon" />
                  <p className="upload-text">
                    Drag and drop target photograph here, or <span>browse files</span>
                  </p>
                  <p style={{ fontSize: '0.75rem', color: '#64748b' }}>Supports JPEG, PNG, WEBP</p>
                </>
              )}
            </div>

            {file && (
              <div className="file-preview-bar">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <FileImage size={16} style={{ color: 'var(--primary)' }} />
                  <span style={{ fontWeight: '500' }}>{file.name}</span>
                  <span style={{ color: '#64748b' }}>({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
                <button 
                  type="button" 
                  onClick={(e) => { e.stopPropagation(); setFile(null); setPreview(''); }} 
                  className="file-remove-btn"
                  disabled={loading}
                >
                  Clear File
                </button>
              </div>
            )}

            <div className="form-group" style={{ marginTop: '1.25rem' }}>
              <label htmlFor="category">Database Categorization Filter</label>
              <select
                id="category"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={loading}
              >
                <option value="all">Search Entire Database (All Lists)</option>
                <option value="criminal">Criminal Suspect Profiles Only</option>
                <option value="missing_person">Missing Persons Register Only</option>
              </select>
            </div>

            <button 
              type="submit" 
              className="btn-primary" 
              style={{ width: '100%' }}
              disabled={loading || !file}
            >
              {loading ? (
                <>
                  <span className="pulse-loader" />
                  <span>Scanning Face Embeddings...</span>
                </>
              ) : (
                <span>Initiate Database Query</span>
              )}
            </button>
          </form>

          {error && (
            <div className="error-banner" style={{ marginTop: '1rem' }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Results Column */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="card-title">
            <ShieldAlert size={20} style={{ color: results.length ? 'var(--status-critical)' : 'var(--status-neutral)' }} />
            <span>Search Query Matches ({results.length})</span>
          </h2>

          <div className="results-grid" style={{ flexGrow: 1, overflowY: 'auto' }}>
            {results.length > 0 ? (
              results.map((candidate) => (
                <div key={candidate.person_id} className="candidate-card">
                  <img
                    src={`${api.baseUrl}/dataset/${candidate.best_reference}`}
                    alt={candidate.name}
                    className="candidate-avatar"
                    onError={(e) => {
                      // Fallback image if it fails to load
                      e.target.src = 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=80&h=80&fit=crop&crop=faces';
                    }}
                  />
                  <div className="candidate-details">
                    <span className="candidate-name">{candidate.name}</span>
                    <div className="candidate-meta">
                      <span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>
                        ID: {candidate.person_id}
                      </span>
                      <span className={`badge ${candidate.category === 'criminal' ? 'badge-critical' : 'badge-warning'}`}>
                        {candidate.category === 'missing_person' ? 'Missing Person' : 'Criminal Suspect'}
                      </span>
                      <span className={`badge ${candidate.review_recommended ? 'badge-critical' : 'badge-neutral'}`}>
                        {candidate.confidence}
                      </span>
                    </div>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      References matching in cluster: {candidate.reference_count}
                    </span>
                  </div>

                  <div className="similarity-indicator">
                    <span className="similarity-val">{(candidate.similarity * 100).toFixed(1)}%</span>
                    <span className="similarity-label">Similarity</span>
                    <div className="match-bar-bg">
                      <div 
                        className="match-bar-fill" 
                        style={{ 
                          width: `${candidate.similarity * 100}%`,
                          backgroundColor: candidate.similarity > 0.75 
                            ? 'var(--status-success)' 
                            : candidate.similarity >= 0.5 
                              ? 'var(--status-warning)' 
                              : 'var(--status-neutral)'
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', padding: '2rem 0' }}>
                <Camera size={48} style={{ marginBottom: '1rem', opacity: '0.5' }} />
                <p style={{ textAlign: 'center', fontSize: '0.9rem' }}>
                  No active query profiles loaded.<br />Select a photo file to run candidate face searches.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
