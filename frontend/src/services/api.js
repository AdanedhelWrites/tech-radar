import axios from 'axios'

const API_URL = '/api'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// News API
export const newsApi = {
  getNews: () => api.get('/news/'),
  fetchNews: (data) => api.post('/fetch/', data),
  clearCache: () => api.post('/clear/'),
  getStats: () => api.get('/stats/'),
  exportNews: () => api.get('/export/'),
}

// CVE API
export const cveApi = {
  getCVEs: () => api.get('/cve/'),
  fetchCVEs: (data) => api.post('/cve/fetch/', data),
  clearCache: () => api.post('/cve/clear/'),
  getStats: () => api.get('/cve/stats/'),
  exportCVEs: () => api.get('/cve/export/'),
}

// Kubernetes API
export const k8sApi = {
  getK8s: () => api.get('/k8s/'),
  fetchK8s: (data) => api.post('/k8s/fetch/', data),
  clearCache: () => api.post('/k8s/clear/'),
  getStats: () => api.get('/k8s/stats/'),
  exportK8s: () => api.get('/k8s/export/'),
}

// SRE API
export const sreApi = {
  getSRE: () => api.get('/sre/'),
  fetchSRE: (data) => api.post('/sre/fetch/', data),
  clearCache: () => api.post('/sre/clear/'),
  getStats: () => api.get('/sre/stats/'),
  exportSRE: () => api.get('/sre/export/'),
}

// DevTools API
export const devtoolsApi = {
  getDevTools: () => api.get('/devtools/'),
  fetchDevTools: (data) => api.post('/devtools/fetch/', data),
  clearCache: () => api.post('/devtools/clear/'),
  getStats: () => api.get('/devtools/stats/'),
  exportDevTools: () => api.get('/devtools/export/'),
}

// AI API
export const aiApi = {
  getAINews: () => api.get('/ai/'),
  fetchAINews: (data) => api.post('/ai/fetch/', data),
  clearCache: () => api.post('/ai/clear/'),
  getStats: () => api.get('/ai/stats/'),
  exportAINews: () => api.get('/ai/export/'),
}

export default api
