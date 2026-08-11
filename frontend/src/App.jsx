import React, { useState, useEffect } from 'react';
import { api } from './api';
import Sidebar from './components/Sidebar';
import Login from './components/Login';
import SearchPhoto from './components/SearchPhoto';
import SearchSketch from './components/SearchSketch';
import CctvScanner from './components/CctvScanner';
import SightingsMap from './components/SightingsMap';
import DatabaseRegistry from './components/DatabaseRegistry';
import AuditTrail from './components/AuditTrail';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(api.isAuthenticated());
  const [userRole, setUserRole] = useState(api.getCurrentUserRole());
  const [activeTab, setActiveTab] = useState('search');

  useEffect(() => {
    const handleAuthChange = () => {
      const auth = api.isAuthenticated();
      setIsAuthenticated(auth);
      setUserRole(api.getCurrentUserRole());
      if (auth) {
        setActiveTab('search');
      }
    };

    window.addEventListener('auth_change', handleAuthChange);
    return () => window.removeEventListener('auth_change', handleAuthChange);
  }, []);

  if (!isAuthenticated) {
    return <Login />;
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'search':
        return <SearchPhoto />;
      case 'sketch':
        return <SearchSketch />;
      case 'cctv':
        return <CctvScanner />;
      case 'map':
        return <SightingsMap />;
      case 'database':
        return userRole === 'admin' ? <DatabaseRegistry /> : <SearchPhoto />;
      case 'audit':
        return userRole === 'admin' ? <AuditTrail /> : <SearchPhoto />;
      default:
        return <SearchPhoto />;
    }
  };

  return (
    <div className="app-container">
      <Sidebar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        userRole={userRole} 
      />
      <main className="main-content">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
