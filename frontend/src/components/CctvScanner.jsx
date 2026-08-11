import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import { 
  Tv, 
  Upload, 
  FileVideo, 
  FileImage, 
  AlertCircle, 
  Play, 
  Activity, 
  Clock, 
  Compass 
} from 'lucide-react';

export default function CctvScanner() {
  // Config state
  const [videoFile, setVideoFile] = useState(null);
  const [targetFile, setTargetFile] = useState(null);
  const [cameraId, setCameraId] = useState('demo_corridor');
  const [cameras, setCameras] = useState({});
  const [interval, setIntervalVal] = useState(0.5);
  const [threshold, setThreshold] = useState(0.45);

  // Flow control state
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState('');
  const [status, setStatus] = useState(''); // 'processing' | 'done' | 'failed'
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);
  const [matches, setMatches] = useState([]);
  
  // Media states
  const [videoUrl, setVideoUrl] = useState('');
  const [evidenceUrls, setEvidenceUrls] = useState({});
  const [activeTimestamp, setActiveTimestamp] = useState(0);

  const videoRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // Load cameras on mount
  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const data = await api.getCameraLocations();
        setCameras(data);
        if (Object.keys(data).length > 0) {
          setCameraId(Object.keys(data)[0]);
        }
      } catch (err) {
        console.error('Failed to load camera locations', err);
      }
    };
    fetchCameras();

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  // Poll job status
  const startPolling = (id) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    
    pollIntervalRef.current = setInterval(async () => {
      try {
        const data = await api.getCctvResults(id);
        setStatus(data.status);
        
        if (data.status === 'done') {
          clearInterval(pollIntervalRef.current);
          setLoading(false);
          setStats(data.statistics);
          setMatches(data.matches || []);
          
          // Load media resources as blobs securely
          loadReviewVideo(id);
          loadEvidenceCrops(id, data.matches || []);
        } else if (data.status === 'failed') {
          clearInterval(pollIntervalRef.current);
          setLoading(false);
          setError(data.error || 'CCTV scan job failed');
        }
      } catch (err) {
        clearInterval(pollIntervalRef.current);
        setLoading(false);
        setError(err.message || 'Error tracking scan progress');
      }
    }, 2000);
  };

  const loadReviewVideo = async (id) => {
    try {
      const url = await api.fetchMediaBlob(api.getReviewVideoUrl(id));
      setVideoUrl(url);
    } catch (err) {
      console.error('Failed to retrieve review video', err);
      setError('Could not load review footage. ' + err.message);
    }
  };

  const loadEvidenceCrops = async (id, matchList) => {
    const urls = {};
    for (const match of matchList) {
      if (match.evidence_image && !urls[match.evidence_image]) {
        try {
          const url = await api.fetchMediaBlob(api.getEvidenceUrl(id, match.evidence_image));
          urls[match.evidence_image] = url;
        } catch (err) {
          console.error(`Failed to load evidence crop: ${match.evidence_image}`, err);
        }
      }
    }
    setEvidenceUrls(urls);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!videoFile || !targetFile) return;

    setLoading(true);
    setError('');
    setJobId('');
    setStatus('');
    setStats(null);
    setMatches([]);
    setVideoUrl('');
    setEvidenceUrls({});

    try {
      const response = await api.cctvScan(videoFile, targetFile, cameraId, interval, threshold);
      setJobId(response.job_id);
      setStatus(response.status);
      startPolling(response.job_id);
    } catch (err) {
      setError(err.message || 'CCTV scan submission failed');
      setLoading(false);
    }
  };

  // Jump video playhead to specific second
  const jumpToTime = (seconds) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play().catch(() => {});
    }
  };

  // Keep active timeline match in sync with video runtime
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const time = videoRef.current.currentTime;
      // Find matching timestamp closest to current runtime
      let active = null;
      let minDiff = 0.5; // max half second tolerance
      
      matches.forEach(m => {
        const diff = Math.abs(m.timestamp_sec - time);
        if (diff < minDiff) {
          minDiff = diff;
          active = m.timestamp_sec;
        }
      });
      
      if (active !== null) {
        setActiveTimestamp(active);
      }
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">CCTV Scanner & Analysis</h1>
          <p className="page-desc">Scan surveillance footage for specific suspect faces and index matches to a temporal timeline.</p>
        </div>
      </div>

      {!videoUrl && status !== 'processing' ? (
        /* Configuration Form */
        <div className="card" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <h2 className="card-title">
            <Tv size={20} style={{ color: 'var(--primary)' }} />
            <span>Configure CCTV Scan Parameters</span>
          </h2>

          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              {/* Surveillance Video File */}
              <div className="form-group">
                <label>Surveillance Video Input</label>
                <div className="upload-dropzone" style={{ padding: '1.5rem 1rem' }}>
                  <input
                    type="file"
                    style={{ display: 'none' }}
                    id="cctv-video-upload"
                    accept="video/*"
                    onChange={(e) => setVideoFile(e.target.files[0])}
                  />
                  <label htmlFor="cctv-video-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                    <FileVideo size={24} style={{ color: videoFile ? 'var(--status-success)' : '#64748b' }} />
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      {videoFile ? videoFile.name : 'Select video footage'}
                    </span>
                  </label>
                </div>
              </div>

              {/* Target suspect Face */}
              <div className="form-group">
                <label>Target Suspect Face Photo</label>
                <div className="upload-dropzone" style={{ padding: '1.5rem 1rem' }}>
                  <input
                    type="file"
                    style={{ display: 'none' }}
                    id="cctv-target-upload"
                    accept="image/*"
                    onChange={(e) => setTargetFile(e.target.files[0])}
                  />
                  <label htmlFor="cctv-target-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
                    <FileImage size={24} style={{ color: targetFile ? 'var(--status-success)' : '#64748b' }} />
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      {targetFile ? targetFile.name : 'Select target face'}
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <div className="form-grid" style={{ marginTop: '1rem' }}>
              <div className="form-group">
                <label htmlFor="camera">Camera Identifier</label>
                <select
                  id="camera"
                  value={cameraId}
                  onChange={(e) => setCameraId(e.target.value)}
                >
                  {Object.entries(cameras).map(([id, info]) => (
                    <option key={id} value={id}>{info.label} ({id})</option>
                  ))}
                  {Object.keys(cameras).length === 0 && (
                    <option value="demo_corridor">Demo Corridor (Default)</option>
                  )}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="interval">Frame Scan Interval</label>
                <div className="slider-container">
                  <input
                    type="range"
                    id="interval"
                    min="0.1"
                    max="2.0"
                    step="0.1"
                    value={interval}
                    onChange={(e) => setIntervalVal(parseFloat(e.target.value))}
                  />
                  <span className="slider-val">{interval}s</span>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="threshold">Recognition Threshold</label>
                <div className="slider-container">
                  <input
                    type="range"
                    id="threshold"
                    min="0.30"
                    max="0.80"
                    step="0.05"
                    value={threshold}
                    onChange={(e) => setThreshold(parseFloat(e.target.value))}
                  />
                  <span className="slider-val">{threshold}</span>
                </div>
              </div>
            </div>

            <button 
              type="submit" 
              className="btn-primary" 
              style={{ width: '100%', marginTop: '1rem' }}
              disabled={loading || !videoFile || !targetFile}
            >
              <span>Initiate Spatial Surveillance Scan</span>
            </button>
          </form>

          {error && (
            <div className="error-banner" style={{ marginTop: '1.25rem' }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}
        </div>
      ) : status === 'processing' ? (
        /* Progress Monitor */
        <div className="card" style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'center', padding: '3rem 2rem' }}>
          <Activity size={48} className="upload-icon" style={{ animation: 'pulse 1.5s infinite ease-in-out', color: 'var(--primary)' }} />
          <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: '#fff', marginTop: '1.5rem' }}>Surveillance Scan Processing</h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.5rem' }}>
            Job ID: <code style={{ color: 'var(--primary)' }}>{jobId}</code>
          </p>
          <div className="match-bar-bg" style={{ width: '200px', margin: '1.5rem auto' }}>
            <div className="match-bar-fill" style={{ width: '100%', animation: 'pulse 1.5s infinite ease-in-out' }} />
          </div>
          <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
            Decoding frames, extracting features, and mapping face vectors in the background. Please remain on this screen.
          </p>
        </div>
      ) : (
        /* Scan Finished: Video Player + Timeline Grid */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Metadata banner */}
          <div className="card" style={{ padding: '1rem' }}>
            <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', textAlign: 'center' }}>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '600' }}>Camera Node</span>
                <p style={{ fontSize: '0.9rem', fontWeight: '600', color: '#fff', marginTop: '0.15rem' }}>
                  {cameras[cameraId]?.label || cameraId}
                </p>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '600' }}>Frames Scanned</span>
                <p style={{ fontSize: '0.9rem', fontWeight: '600', color: '#fff', marginTop: '0.15rem' }}>
                  {stats?.frames_sampled} / {stats?.frames_read}
                </p>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '600' }}>Faces Detected</span>
                <p style={{ fontSize: '0.9rem', fontWeight: '600', color: '#fff', marginTop: '0.15rem' }}>
                  {stats?.faces_detected}
                </p>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '600' }}>Scan Rate</span>
                <p style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--primary)', marginTop: '0.15rem' }}>
                  {stats?.fps?.toFixed(1)} fps
                </p>
              </div>
              <div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '600' }}>Match Candidates</span>
                <p style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--status-critical)', marginTop: '0.15rem' }}>
                  {matches.length}
                </p>
              </div>
            </div>
          </div>

          <div className="cctv-viewer-grid">
            {/* Playback Container */}
            <div className="cctv-player-container">
              <div className="cctv-video-frame">
                <video
                  ref={videoRef}
                  src={videoUrl}
                  controls
                  className="cctv-video-element"
                  onTimeUpdate={handleTimeUpdate}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  Disclaimer: Annotations denote algorithm leads. Matches require human confirmation.
                </span>
                <button 
                  className="btn-primary" 
                  style={{ padding: '0.4rem 1rem', fontSize: '0.8rem' }}
                  onClick={() => {
                    setVideoUrl('');
                    setStatus('');
                    setStats(null);
                    setMatches([]);
                    setVideoFile(null);
                    setTargetFile(null);
                  }}
                >
                  Analyze New Footage
                </button>
              </div>
            </div>

            {/* Match Timeline */}
            <div className="cctv-timeline">
              <div className="cctv-timeline-header">
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Clock size={16} />
                  <span>Detections Timeline</span>
                </span>
                <span className="badge badge-critical" style={{ fontSize: '0.6rem' }}>
                  {matches.length} Alerts
                </span>
              </div>

              <div className="cctv-timeline-list">
                {matches.length > 0 ? (
                  matches.map((match, idx) => {
                    const isActive = activeTimestamp === match.timestamp_sec;
                    return (
                      <div 
                        key={idx} 
                        className={`timeline-event-card ${isActive ? 'active' : ''}`}
                        onClick={() => jumpToTime(match.timestamp_sec)}
                      >
                        <img 
                          src={evidenceUrls[match.evidence_image] || 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=50&h=50&fit=crop&crop=faces'} 
                          alt="Face Crop" 
                          className="timeline-event-crop" 
                        />
                        <div className="timeline-event-details">
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span className="timeline-event-time">
                              {Math.floor(match.timestamp_sec / 60)}:
                              {String(Math.floor(match.timestamp_sec % 60)).padStart(2, '0')}s
                            </span>
                            <span 
                              className={`badge ${match.similarity >= 0.75 ? 'badge-critical' : 'badge-warning'}`}
                              style={{ fontSize: '0.6rem', padding: '0.05rem 0.25rem' }}
                            >
                              {(match.similarity * 100).toFixed(0)}% Match
                            </span>
                          </div>
                          <span className="timeline-event-score">
                            Frame: {match.frame_number} | Source: {match.detection_source}
                          </span>
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', padding: '2rem 1rem', textAlign: 'center' }}>
                    <Compass size={32} style={{ marginBottom: '0.5rem', opacity: '0.4' }} />
                    <p style={{ fontSize: '0.8rem' }}>No face matches crossed the {threshold} similarity threshold in this video.</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
