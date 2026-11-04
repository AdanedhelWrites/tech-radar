import axios from 'axios'

const API_URL = '/api'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Django admin oturumu acikken POST isteklerinde CSRF token'i gonder
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  // Asili kalan istek hata ile biter: liste yenilemesi (useListeSorgusu) yanit beklerken tur
  // atladigi icin zaman asimi olmasa tek bir takilan istek otomatik yenilemeyi kalici durdururdu
  timeout: 30000,
})

// Liste uclari (getNews, getCVEs ...) istege bagli sorgu parametresi alir (2026-11-05):
// {gun, sirala, sayfa, boyut, kaynak, onem, kategori}; parametresiz cagri en yeni 25 kaydi dondurur.

// News API
export const newsApi = {
  getNews: (params) => api.get('/news/', { params }),
  fetchNews: (data) => api.post('/fetch/', data),
  clearCache: () => api.post('/clear/'),
  getStats: () => api.get('/stats/'),
  exportNews: () => api.get('/export/'),
}

// CVE API
export const cveApi = {
  getCVEs: (params) => api.get('/cve/', { params }),
  fetchCVEs: (data) => api.post('/cve/fetch/', data),
  clearCache: () => api.post('/cve/clear/'),
  getStats: () => api.get('/cve/stats/'),
  exportCVEs: () => api.get('/cve/export/'),
}

// Kubernetes API
export const k8sApi = {
  getK8s: (params) => api.get('/k8s/', { params }),
  fetchK8s: (data) => api.post('/k8s/fetch/', data),
  clearCache: () => api.post('/k8s/clear/'),
  getStats: () => api.get('/k8s/stats/'),
  exportK8s: () => api.get('/k8s/export/'),
}

// SRE API
export const sreApi = {
  getSRE: (params) => api.get('/sre/', { params }),
  fetchSRE: (data) => api.post('/sre/fetch/', data),
  clearCache: () => api.post('/sre/clear/'),
  getStats: () => api.get('/sre/stats/'),
  exportSRE: () => api.get('/sre/export/'),
}

// DevTools API
export const devtoolsApi = {
  getDevTools: (params) => api.get('/devtools/', { params }),
  fetchDevTools: (data) => api.post('/devtools/fetch/', data),
  clearCache: () => api.post('/devtools/clear/'),
  getStats: () => api.get('/devtools/stats/'),
  exportDevTools: () => api.get('/devtools/export/'),
}

// AI API
export const aiApi = {
  getAINews: (params) => api.get('/ai/', { params }),
  fetchAINews: (data) => api.post('/ai/fetch/', data),
  clearCache: () => api.post('/ai/clear/'),
  getStats: () => api.get('/ai/stats/'),
  exportAINews: () => api.get('/ai/export/'),
}

// Sunucunun dondurdugu mesaji tercih eder (ornegin soguma: 429 "... N dk sonra tekrar deneyin").
// Mesaj yoksa (ag hatasi vb.) varsayilan metin + axios hatasi gosterilir.
export const istekHataMesaji = (err, varsayilan) =>
  err.response?.data?.message || `${varsayilan}: ${err.message}`

// Saglik seridi (anonim, 60 sn cache'li; 2026-10-14)
export const saglikApi = {
  getSaglik: () => api.get('/saglik/'),
}

// Genel Bakis zafiyet ozeti (2026-10-31). since: son ziyaret (ISO); verilirse yanit new_since_count tasir.
export const ozetApi = {
  getOzet: (since) => api.get('/ozet/', { params: since ? { since } : {} }),
}

export default api
