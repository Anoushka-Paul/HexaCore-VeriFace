const BASE_URL = 'http://localhost:8000';

function getHeaders(isMultipart = false) {
  const token = localStorage.getItem('veriface_token');
  const headers = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!isMultipart) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
}

async function handleResponse(response) {
  if (response.status === 401) {
    // Session expired or unauthorized
    localStorage.removeItem('veriface_token');
    localStorage.removeItem('veriface_role');
    window.dispatchEvent(new Event('auth_change'));
  }
  
  if (!response.ok) {
    let errMsg = 'An error occurred';
    try {
      const errData = await response.json();
      errMsg = errData.detail || errData.message || JSON.stringify(errData);
    } catch {
      errMsg = response.statusText || errMsg;
    }
    throw new Error(errMsg);
  }
  
  return response.json();
}

export const api = {
  baseUrl: BASE_URL,
  
  async login(username, password) {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    const response = await fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      body: formData,
    });
    const data = await handleResponse(response);
    if (data.access_token) {
      localStorage.setItem('veriface_token', data.access_token);
      localStorage.setItem('veriface_role', data.role);
      window.dispatchEvent(new Event('auth_change'));
    }
    return data;
  },

  async register(username, password, role) {
    const response = await fetch(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ username, password, role }),
    });
    return handleResponse(response);
  },

  logout() {
    localStorage.removeItem('veriface_token');
    localStorage.removeItem('veriface_role');
    window.dispatchEvent(new Event('auth_change'));
  },

  getCurrentUserRole() {
    return localStorage.getItem('veriface_role');
  },

  isAuthenticated() {
    return !!localStorage.getItem('veriface_token');
  },

  async getMe() {
    const response = await fetch(`${BASE_URL}/auth/me`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  async searchFace(file, category = 'all') {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('category', category);

    const response = await fetch(`${BASE_URL}/search`, {
      method: 'POST',
      headers: getHeaders(true),
      body: formData,
    });
    return handleResponse(response);
  },

  async sketchSearch(sketchFile, style = 'cufs', category = 'all') {
    const formData = new FormData();
    formData.append('sketch', sketchFile);
    formData.append('style', style);
    formData.append('category', category);

    const response = await fetch(`${BASE_URL}/sketch-search`, {
      method: 'POST',
      headers: getHeaders(true),
      body: formData,
    });
    return handleResponse(response);
  },

  async cctvScan(videoFile, targetFile, cameraId, interval = 0.5, threshold = 0.45) {
    const formData = new FormData();
    formData.append('video', videoFile);
    formData.append('target', targetFile);
    formData.append('camera_id', cameraId);
    formData.append('interval', String(interval));
    formData.append('threshold', String(threshold));

    const response = await fetch(`${BASE_URL}/cctv-scan`, {
      method: 'POST',
      headers: getHeaders(true),
      body: formData,
    });
    return handleResponse(response);
  },

  async getCctvResults(jobId) {
    const response = await fetch(`${BASE_URL}/cctv-jobs/${jobId}/results`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  async fetchMediaBlob(relativeUrl) {
    const token = localStorage.getItem('veriface_token');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const response = await fetch(`${BASE_URL}${relativeUrl}`, { headers });
    if (!response.ok) {
      throw new Error(`Failed to fetch media: ${response.statusText}`);
    }
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  },

  getReviewVideoUrl(jobId) {
    return `/cctv-jobs/${jobId}/review-video`;
  },

  getEvidenceUrl(jobId, filename) {
    return `/cctv-jobs/${jobId}/evidence/${filename}`;
  },

  async addPerson(name, category, file, personId = '') {
    const formData = new FormData();
    formData.append('name', name);
    formData.append('category', category);
    formData.append('file', file);
    if (personId) {
      formData.append('person_id', personId);
    }

    const response = await fetch(`${BASE_URL}/add-person`, {
      method: 'POST',
      headers: getHeaders(true),
      body: formData,
    });
    return handleResponse(response);
  },

  async getAudit() {
    const response = await fetch(`${BASE_URL}/audit`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  async getSightings(personId = '', cameraId = '') {
    const params = new URLSearchParams();
    if (personId) params.append('person_id', personId);
    if (cameraId) params.append('camera_id', cameraId);

    const query = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${BASE_URL}/sightings${query}`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  async getCameraLocations() {
    const response = await fetch(`${BASE_URL}/camera-locations`, {
      method: 'GET',
      headers: getHeaders(),
    });
    return handleResponse(response);
  },

  async getHealth() {
    const response = await fetch(`${BASE_URL}/health`, {
      method: 'GET',
    });
    return handleResponse(response);
  }
};
