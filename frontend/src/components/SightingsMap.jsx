import React, { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { api } from '../api';
import { Compass, Camera, AlertCircle, Clock, MapPin, Search } from 'lucide-react';

// Secure Leaflet default marker icon assets from CDN to avoid bundler resolution errors
const cameraIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

const alertIcon = L.icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Helper component to programmatically pan/zoom map view
function ChangeView({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, zoom || map.getZoom(), { animate: true, duration: 1 });
    }
  }, [center, zoom]);
  return null;
}

export default function SightingsMap() {
  const [cameras, setCameras] = useState({});
  const [sightings, setSightings] = useState([]);
  const [filterPerson, setFilterPerson] = useState('');
  const [filterCamera, setFilterCamera] = useState('');
  const [mapCenter, setMapCenter] = useState([40.7128, -74.0060]); // NY default
  const [mapZoom, setMapZoom] = useState(14);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadMapData = async () => {
    setLoading(true);
    setError('');
    try {
      const locations = await api.getCameraLocations();
      setCameras(locations);
      
      // Calculate map bounds/center if camera locations exist
      const keys = Object.keys(locations);
      if (keys.length > 0) {
        const firstCam = locations[keys[0]];
        setMapCenter([firstCam.lat, firstCam.lng]);
      }

      const activeSightings = await api.getSightings();
      setSightings(activeSightings);
    } catch (err) {
      setError(err.message || 'Failed to load surveillance assets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMapData();
  }, []);

  const handleSightingClick = (sighting) => {
    if (sighting.lat && sighting.lng) {
      setMapCenter([sighting.lat, sighting.lng]);
      setMapZoom(16);
    }
  };

  // Filter sightings logic
  const filteredSightings = sightings.filter(s => {
    const matchesPerson = !filterPerson || (s.person_id && s.person_id.toLowerCase().includes(filterPerson.toLowerCase()));
    const matchesCamera = !filterCamera || (s.camera_id && s.camera_id.toLowerCase().includes(filterCamera.toLowerCase()));
    return matchesPerson && matchesCamera;
  });

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Geo-Spatial Sightings Map</h1>
          <p className="page-desc">Track real-time candidate sightings populated from CCTV scan jobs on an interactive surveillance grid.</p>
        </div>
      </div>

      {error && (
        <div className="error-banner" style={{ marginBottom: '1rem' }}>
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <div className="map-container">
        {/* Leaflet Map Grid */}
        <div className="leaflet-map-wrapper">
          <MapContainer center={mapCenter} zoom={mapZoom} style={{ height: '100%', width: '100%' }}>
            <ChangeView center={mapCenter} zoom={mapZoom} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {Object.entries(cameras).map(([id, info]) => {
              // Check if camera has any sightings
              const cameraSightings = sightings.filter(s => s.camera_id === id);
              const hasAlerts = cameraSightings.length > 0;
              
              return (
                <Marker 
                  key={id} 
                  position={[info.lat, info.lng]}
                  icon={hasAlerts ? alertIcon : cameraIcon}
                >
                  <Popup>
                    <div style={{ color: '#fff', fontSize: '0.85rem' }}>
                      <strong style={{ fontSize: '0.95rem', color: 'var(--primary)' }}>{info.label}</strong>
                      <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0.2rem 0' }}>Camera Node: {id}</p>
                      
                      <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.75rem', textTransform: 'uppercase' }}>Recent Sightings:</span>
                        {cameraSightings.length > 0 ? (
                          <ul style={{ paddingLeft: '0.75rem', listStyleType: 'disc', marginTop: '0.25rem' }}>
                            {cameraSightings.slice(0, 3).map((s, idx) => (
                              <li key={idx} style={{ fontSize: '0.75rem', margin: '0.15rem 0' }}>
                                Match ID: {s.person_id || 'Unknown'} ({(s.similarity * 100).toFixed(0)}%)
                                <br />
                                <span style={{ color: '#64748b' }}>{new Date(s.timestamp).toLocaleString()}</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p style={{ fontStyle: 'italic', color: '#64748b', fontSize: '0.75rem' }}>No recent alarms triggered.</p>
                        )}
                      </div>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>

        {/* Map Sidebar Query Panels */}
        <div className="map-sidebar">
          {/* Query Filters */}
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: '600', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginBottom: '0.75rem' }}>
              Surveillance Filters
            </span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-main)', border: '1px solid var(--border-color)', padding: '0.4rem 0.75rem', borderRadius: '6px' }}>
                <Search size={14} style={{ color: '#64748b' }} />
                <input
                  type="text"
                  placeholder="Filter by Suspect ID..."
                  value={filterPerson}
                  onChange={(e) => setFilterPerson(e.target.value)}
                  style={{ border: 'none', background: 'transparent', padding: '0', fontSize: '0.8rem', width: '100%' }}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--bg-main)', border: '1px solid var(--border-color)', padding: '0.4rem 0.75rem', borderRadius: '6px' }}>
                <Camera size={14} style={{ color: '#64748b' }} />
                <input
                  type="text"
                  placeholder="Filter by Camera ID..."
                  value={filterCamera}
                  onChange={(e) => setFilterCamera(e.target.value)}
                  style={{ border: 'none', background: 'transparent', padding: '0', fontSize: '0.8rem', width: '100%' }}
                />
              </div>
            </div>
          </div>

          {/* Sightings Feed */}
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--border-color)', fontWeight: '600', fontSize: '0.8rem', textTransform: 'uppercase', color: '#94a3b8' }}>
            Alert Log Timeline ({filteredSightings.length})
          </div>
          
          <div style={{ flexGrow: 1, overflowY: 'auto', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {filteredSightings.length > 0 ? (
              filteredSightings.map((s) => (
                <div 
                  key={s.id} 
                  className="timeline-event-card"
                  style={{ gridTemplateColumns: '1fr' }}
                  onClick={() => handleSightingClick(s)}
                >
                  <div className="timeline-event-details">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.2rem' }}>
                      <span className="badge badge-critical" style={{ fontSize: '0.6rem', padding: '0.05rem 0.25rem' }}>
                        {(s.similarity * 100).toFixed(0)}% Sighting
                      </span>
                      <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '0.15rem' }}>
                        <Clock size={10} />
                        {s.video_time_sec !== null ? `${Math.floor(s.video_time_sec / 60)}:${String(Math.floor(s.video_time_sec % 60)).padStart(2, '0')}s` : 'Live'}
                      </span>
                    </div>
                    
                    <p style={{ fontSize: '0.85rem', fontWeight: '600', color: '#fff' }}>
                      Suspect ID: {s.person_id || 'Unknown'}
                    </p>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                      <MapPin size={12} style={{ color: 'var(--primary)' }} />
                      <span>{s.label || s.camera_id}</span>
                    </div>

                    <span style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '0.25rem', fontFamily: 'monospace' }}>
                      {new Date(s.timestamp).toLocaleString()}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#64748b', textAlign: 'center', padding: '2rem 0' }}>
                <Compass size={32} style={{ opacity: '0.3', marginBottom: '0.5rem' }} />
                <p style={{ fontSize: '0.8rem' }}>No logged sightings matching criteria found.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
