import React, { useState } from 'react';
import { api } from '../api';
import { Shield, Eye, EyeOff, AlertTriangle } from 'lucide-react';

export default function Login() {
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('officer');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      if (isRegistering) {
        await api.register(username, password, role);
        setSuccess('Account created successfully. Please login.');
        setIsRegistering(false);
        setUsername('');
        setPassword('');
      } else {
        await api.login(username, password);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card">
        <div className="auth-header">
          <Shield size={42} className="upload-icon" style={{ color: 'var(--primary)' }} />
          <h1 className="auth-title">VeriFace</h1>
          <p className="auth-subtitle">Tactical Face Matching & Verification Database</p>
        </div>

        {error && (
          <div className="error-banner">
            <AlertTriangle size={16} />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="badge badge-success" style={{ display: 'flex', width: '100%', padding: '0.75rem', marginBottom: '1.25rem', justifyContent: 'center' }}>
            {success}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Officer Identification / Username</label>
            <input
              type="text"
              id="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g., Det_Smith"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Database Access Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{ width: '100%', paddingRight: '2.5rem' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '0.75rem',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {isRegistering && (
            <div className="form-group">
              <label htmlFor="role">Security Role Assignment</label>
              <select
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="officer">Officer (Standard search permission)</option>
                <option value="admin">Administrator (Database updates + logs permission)</option>
              </select>
            </div>
          )}

          <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.75rem' }} disabled={loading}>
            {loading ? 'Processing...' : isRegistering ? 'Register Credentials' : 'Access Database'}
          </button>
        </form>

        <div className="auth-toggle">
          {isRegistering ? (
            <p>
              Already registered?
              <button type="button" onClick={() => { setIsRegistering(false); setError(''); }}>Sign In</button>
            </p>
          ) : (
            <p>
              New station setup?
              <button type="button" onClick={() => { setIsRegistering(true); setError(''); }}>Create Officer Account</button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
