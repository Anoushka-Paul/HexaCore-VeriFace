import React, { useState, useRef } from 'react';
import { api } from '../api';
import { Upload, Brush, AlertCircle, FileImage, ShieldAlert, ArrowRight } from 'lucide-react';

export default function SearchSketch() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState('');
  const [style, setStyle] = useState('cufs');
  const [category, setCategory] = useState('all');
  const [loading, setLoading] = useState(false);
  const [convertedPreview, setConvertedPreview] = useState('');
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
    setConvertedPreview('');

    try {
      const data = await api.sketchSearch(file, style, category);
      if (data.converted_image) {
        setConvertedPreview(data.converted_image);
      }
      setResults(data.results || []);
    } catch (err) {
      setError(err.message || 'Sketch search and matching failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Composite Sketch recognition</h1>
          <p className="page-desc">Process hand-drawn composite suspect sketches through the GAN-synthesis model to query face databases.</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Upload & Model config Column */}
        <div className="card">
          <h2 className="card-title">
            <Brush size={20} style={{ color: 'var(--primary)' }} />
            <span>Sketch Acquisition & GAN settings</span>
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
                    alt="Sketch Preview" 
                    style={{ maxHeight: '200px', maxWidth: '100%', objectFit: 'contain', borderRadius: '8px', border: '1px solid var(--border-color)' }} 
                  />
                  <p className="upload-text" style={{ marginTop: '0.5rem' }}>
                    Click or drag new sketch to replace
                  </p>
                </div>
              ) : (
                <>
                  <Upload size={36} className="upload-icon" />
                  <p className="upload-text">
                    Drag and drop suspect sketch here, or <span>browse files</span>
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

            <div className="form-grid" style={{ marginTop: '1.25rem' }}>
              <div className="form-group">
                <label htmlFor="style">Sketch GAN Model</label>
                <select
                  id="style"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  disabled={loading}
                >
                  <option value="cufs">CUFS (Standard conversion)</option>
                  <option value="cufsf">CUFSF (Enhanced texture model)</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="category">Target Registry Filter</label>
                <select
                  id="category"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  disabled={loading}
                >
                  <option value="all">Search All Profiles</option>
                  <option value="criminal">Suspects Only</option>
                  <option value="missing_person">Missing Persons Only</option>
                </select>
              </div>
            </div>

            <button 
              type="submit" 
              className="btn-primary" 
              style={{ width: '100%', marginTop: '0.5rem' }}
              disabled={loading || !file}
            >
              {loading ? (
                <>
                  <span className="pulse-loader" />
                  <span>Synthesizing Face & Matching...</span>
                </>
              ) : (
                <span>Convert Sketch & Search</span>
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

        {/* Results & Conversion Column */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <h2 className="card-title">
            <ShieldAlert size={20} style={{ color: results.length ? 'var(--status-critical)' : 'var(--status-neutral)' }} />
            <span>Synthesis Verification & Matches ({results.length})</span>
          </h2>

          {/* Side by side original / GAN output */}
          {convertedPreview && preview && (
            <div className="comparison-layout">
              <div className="comparison-box">
                <img src={preview} alt="Original Sketch" className="comparison-image" />
                <span className="comparison-label">Composite Sketch</span>
              </div>
              <div 
                className="comparison-box" 
                style={{ 
                  borderColor: 'var(--primary)', 
                  boxShadow: '0 0 10px rgba(56, 189, 248, 0.1)' 
                }}
              >
                <img src={convertedPreview} alt="GAN Photo Output" className="comparison-image" />
                <span className="comparison-label" style={{ color: 'var(--primary)' }}>GAN Photo Synthesis</span>
              </div>
            </div>
          )}

          <div className="results-grid" style={{ flexGrow: 1, overflowY: 'auto' }}>
            {results.length > 0 ? (
              results.map((candidate) => (
                <div key={candidate.person_id} className="candidate-card">
                  <img
                    src={`${api.baseUrl}/dataset/${candidate.best_reference}`}
                    alt={candidate.name}
                    className="candidate-avatar"
                    onError={(e) => {
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
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', padding: '2rem 0', flexGrow: 1 }}>
                <Brush size={48} style={{ marginBottom: '1rem', opacity: '0.5' }} />
                <p style={{ textAlign: 'center', fontSize: '0.9rem' }}>
                  No active query profiles loaded.<br />Load a suspect sketch to run the face translation and search.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
