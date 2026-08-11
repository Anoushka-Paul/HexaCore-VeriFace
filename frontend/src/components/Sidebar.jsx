import React from 'react';
import { api } from '../api';
import { 
  Shield, 
  Camera, 
  Brush, 
  Tv, 
  Database, 
  History, 
  MapPin, 
  LogOut 
} from 'lucide-react';

export default function Sidebar({ activeTab, setActiveTab, userRole }) {
  const isAdmin = userRole === 'admin';

  const menuItems = [
    { id: 'search', label: 'Photo Search', icon: Camera, role: ['officer', 'admin'] },
    { id: 'sketch', label: 'Sketch Search', icon: Brush, role: ['officer', 'admin'] },
    { id: 'cctv', label: 'CCTV Scanner', icon: Tv, role: ['officer', 'admin'] },
    { id: 'map', label: 'Sightings Map', icon: MapPin, role: ['officer', 'admin'] },
    { id: 'database', label: 'Suspect Registry', icon: Database, role: ['admin'] },
    { id: 'audit', label: 'Audit Log', icon: History, role: ['admin'] }
  ];

  return (
    <div className="sidebar">
      <div>
        <div className="sidebar-header">
          <Shield size={24} style={{ color: 'var(--primary)' }} />
          <span className="sidebar-title">VeriFace</span>
          <span className="sidebar-badge">{userRole}</span>
        </div>

        <nav className="sidebar-menu">
          {menuItems.map((item) => {
            if (!item.role.includes(userRole)) return null;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`menu-item ${activeTab === item.id ? 'active' : ''}`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-footer">
        <div className="user-info">
          <span className="user-name">Station Operator</span>
          <span className="user-role">{userRole} Account</span>
        </div>
        <button onClick={() => api.logout()} className="btn-logout">
          <LogOut size={16} />
          <span>Disconnect Session</span>
        </button>
      </div>
    </div>
  );
}
