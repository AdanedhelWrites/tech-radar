import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import {
  Container, Row, Col, Card, Button, Form,
  Badge, Spinner, Alert, Modal
} from 'react-bootstrap'
import {
  FaDownload, FaSync, FaTrash, FaFileExport,
  FaShieldAlt, FaChartBar, FaCogs, FaExclamationTriangle,
  FaCalendar, FaExternalLinkAlt,
  FaDatabase, FaGithub, FaShieldVirus, FaGlobe, FaClock
} from 'react-icons/fa'
import { cveApi } from '../services/api'

const sources = [
  { id: 'source1', name: 'NVD', value: 'NVD', icon: FaDatabase, color: '#3498db' },
  { id: 'source2', name: 'GitHub Advisory', value: 'GitHub Advisory', icon: FaGithub, color: '#e74c3c' },
  { id: 'source3', name: 'Tenable', value: 'Tenable', icon: FaShieldVirus, color: '#00b894' },
  { id: 'source4', name: 'CIRCL', value: 'CIRCL', icon: FaGlobe, color: '#f39c12' },
  { id: 'source5', name: 'NVD Güncel', value: 'NVD Güncel', icon: FaClock, color: '#6c5ce7' },
]

function CVEComponent() {
  const [cves, setCVEs] = useState([])
  const [selectedCVE, setSelectedCVE] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({
    total: 0,
    by_source: {},
    by_severity: {},
    last_update: null
  })
  const [days, setDays] = useState(7)
  const [selectedSources, setSelectedSources] = useState(
    sources.reduce((acc, s) => ({ ...acc, [s.value]: true }), {})
  )
  const [severityFilter, setSeverityFilter] = useState('all')

  useEffect(() => {
    loadCVEs()
    loadStats()
  }, [])

  const loadCVEs = async () => {
    try {
      setLoading(true)
      const response = await cveApi.getCVEs()
      if (response.data.success) {
        setCVEs(response.data.data)
      }
    } catch (err) {
      setError('CVE verileri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await cveApi.getStats()
      if (response.data.success) {
        setStats(response.data)
      }
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }

  const handleFetchCVEs = async () => {
    const activeSources = sources
      .filter(s => selectedSources[s.value])
      .map(s => s.value)

    if (activeSources.length === 0) {
      setError('Lütfen en az bir kaynak seçin!')
      return
    }

    try {
      setFetching(true)
      setError(null)


      // CVE'leri çek
      const response = await cveApi.fetchCVEs({
        days: parseInt(days),
        sources: activeSources
      })

      if (response.data.success) {
        setCVEs(response.data.data)
        loadStats()
        toast.success("Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError('CVE verileri getirilirken hata oluştu: ' + err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm CVE verileri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await cveApi.clearCache()
      setCVEs([])
      setSelectedCVE(null)
      loadStats()
      toast.success("Veriler başarıyla temizlendi", { icon: "🗑️" })
    } catch (err) {
      setError('Sıfırlama sırasında hata oluştu')
    }
  }

  const handleExport = async () => {
    try {
      const response = await cveApi.exportCVEs()
      if (response.data.success) {
        const items = response.data.data
        const date = new Date().toLocaleDateString('tr-TR')
        const severityColor = (s) => {
          const colors = { 'Kritik': '#dc3545', 'Yüksek': '#fd7e14', 'Orta': '#ffc107', 'Düşük': '#28a745' }
          return colors[s] || '#6c757d'
        }
        const html = `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>CVE Zafiyet Raporu - ${date}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: #5b86a7; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; color: #fff; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .cveid { color: #5b86a7; font-weight: bold; font-size: 0.9rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc; }
  .article a { color: #5b86a7; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
  .score { font-weight: bold; font-size: 0.85rem; }
  @media print { body { background: #fff; color: #000; } .article { border-color: #ddd; background: #f9f9f9; } .article h3, .article .content { color: #000; } h1 { color: #333; } }
</style>
</head>
<body>
<h1>CVE Zafiyet Raporu</h1>
<p class="meta">${date} tarihinde oluşturuldu &mdash; ${items.length} zafiyet</p>
${items.map(item => {
          const content = (item.turkish_description || item.original_description || '').replace(/\n/g, '<br>')
          return `<div class="article">
  <span class="cveid">${item.cve_id || ''}</span>
  <span class="badge" style="background:${severityColor(item.severity)}">${item.severity || 'Bilinmiyor'}</span>
  ${item.cvss_score ? `<span class="score">CVSS: ${item.cvss_score}</span>` : ''}
  <span class="date">${item.published_date || ''}</span>
  <h3>${item.turkish_title || item.original_title || ''}</h3>
  <div class="content">${content}</div>
  <a href="${item.link || ''}" target="_blank">Kaynağa Git &rarr;</a>
</div>`
        }).join('\n')}
</body></html>`
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `cve_zafiyet_raporu_${new Date().toISOString().split('T')[0]}.html`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      setError('Dışarı aktarma hatası')
    }
  }

  const toggleSource = (value) => {
    setSelectedSources(prev => ({
      ...prev,
      [value]: !prev[value]
    }))
  }

  const getSeverityClass = (severity) => {
    const severityMap = {
      'Kritik': 'severity-kritik',
      'Yüksek': 'severity-yuksek',
      'Orta': 'severity-orta',
      'Düşük': 'severity-dusuk',
      'Bilinmiyor': 'severity-bilinmiyor',
      'CRITICAL': 'severity-kritik',
      'HIGH': 'severity-yuksek',
      'MEDIUM': 'severity-orta',
      'LOW': 'severity-dusuk',
    }
    return severityMap[severity] || 'severity-bilinmiyor'
  }

  const getCVSSClass = (score) => {
    if (score === null || score === undefined) return ''
    if (score >= 9.0) return 'cvss-critical'
    if (score >= 7.0) return 'cvss-high'
    if (score >= 4.0) return 'cvss-medium'
    return 'cvss-low'
  }

  const severityOptions = [
    { value: 'all', label: 'Tümü', color: '#6c757d' },
    { value: 'critical', label: 'Kritik', color: '#dc3545', min: 9.0, max: 10.0 },
    { value: 'high', label: 'Yüksek', color: '#fd7e14', min: 7.0, max: 8.9 },
    { value: 'medium', label: 'Orta', color: '#ffc107', min: 4.0, max: 6.9 },
    { value: 'low', label: 'Düşük', color: '#28a745', min: 0, max: 3.9 },
  ]

  const filteredCVEs = severityFilter === 'all'
    ? cves
    : cves.filter(cve => {
      const opt = severityOptions.find(o => o.value === severityFilter)
      if (!opt || !cve.cvss_score) return false
      return cve.cvss_score >= opt.min && cve.cvss_score <= opt.max
    })

  const getSourceIcon = (sourceName) => {
    const found = sources.find(s => s.value === sourceName)
    if (found) {
      const IconComp = found.icon
      return <IconComp className="me-1" size={12} />
    }
    return null
  }

  const getSourceColor = (sourceName) => {
    const found = sources.find(s => s.value === sourceName)
    return found ? found.color : '#95a5a6'
  }

  return (
    <Container fluid>
      <Row>
        {/* Sol Panel - Kontroller */}
        <Col md={3}>
          <Card className="mb-4">
            <Card.Header className="bg-danger text-white">
              <h5 className="mb-0"><FaCogs className="me-2" />Kontroller</h5>
            </Card.Header>
            <Card.Body>
              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">Kaç Günlük CVE?</Form.Label>
                <Form.Range
                  min={1}
                  max={15}
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                />
                <div className="text-center">
                  <Badge bg="secondary" className="fs-6">{days} Gün</Badge>
                </div>
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">CVE Kaynakları</Form.Label>
                {sources.map(source => {
                  const IconComp = source.icon
                  return (
                    <Form.Check
                      key={source.id}
                      type="checkbox"
                      id={source.id}
                      checked={selectedSources[source.value]}
                      onChange={() => toggleSource(source.value)}
                      label={
                        <span className="d-flex align-items-center gap-2">
                          <IconComp style={{ color: source.color }} />
                          {source.name}
                        </span>
                      }
                    />
                  )
                })}
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">CVSS Şiddet Filtresi</Form.Label>
                <div className="d-flex flex-wrap gap-1">
                  {severityOptions.map(opt => (
                    <Button
                      key={opt.value}
                      size="sm"
                      variant={severityFilter === opt.value ? 'light' : 'outline-secondary'}
                      className="flex-fill"
                      style={severityFilter === opt.value ? {
                        backgroundColor: opt.color,
                        borderColor: opt.color,
                        color: '#fff',
                        fontWeight: 'bold'
                      } : {}}
                      onClick={() => setSeverityFilter(opt.value)}
                    >
                      {opt.label}
                    </Button>
                  ))}
                </div>
                {severityFilter !== 'all' && (
                  <div className="text-center mt-1">
                    <small className="text-muted">
                      {filteredCVEs.length} / {cves.length} CVE gösteriliyor
                    </small>
                  </div>
                )}
              </Form.Group>

              <Button
                variant="danger"
                className="w-100 mb-2"
                onClick={handleFetchCVEs}
                disabled={fetching}
              >
                {fetching ? (
                  <><Spinner size="sm" className="me-2" />Getiriliyor...</>
                ) : (
                  <><FaDownload className="me-2" />CVE Zafiyetlerini Getir</>
                )}
              </Button>

              <Button
                variant="outline-secondary"
                className="w-100 mb-2"
                onClick={loadCVEs}
                disabled={loading}
              >
                <FaSync className="me-2" />Yenile
              </Button>

              <div className="d-flex gap-2">
                <Button
                  variant="outline-danger"
                  className="flex-fill"
                  size="sm"
                  onClick={handleClearCache}
                  title="Tüm CVE verilerini sil ve sıfırla"
                >
                  <FaTrash className="me-1" />Sıfırla
                </Button>

                <Button
                  variant="outline-warning"
                  className="flex-fill"
                  size="sm"
                  onClick={handleExport}
                  title="CVE zafiyetlerini HTML rapor olarak indir"
                >
                  <FaFileExport className="me-1" />İndir
                </Button>
              </div>
            </Card.Body>
          </Card>

          <Card className="stats-card">
            <Card.Body>
              <h5 className="card-title"><FaChartBar className="me-2" />İstatistikler</h5>
              <div className="mt-3">
                <div className="d-flex justify-content-between mb-2">
                  <span>Toplam CVE:</span>
                  <span className="fw-bold fs-5">{stats.total}</span>
                </div>
                <div className="d-flex justify-content-between mb-2">
                  <span>Son Güncelleme:</span>
                  <span className="fw-bold">
                    {stats.last_update
                      ? new Date(stats.last_update).toLocaleString('tr-TR')
                      : '-'}
                  </span>
                </div>

                <div className="mt-3">
                  <small><strong>Kaynaklar:</strong></small><br />
                  {Object.entries(stats.by_source).map(([source, count]) => (
                    <div key={source} className="d-flex justify-content-between mt-1">
                      <span>{source}:</span>
                      <span className="fw-bold">{count}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-3">
                  <small><strong>Şiddet Dağılımı:</strong></small><br />
                  {Object.entries(stats.by_severity).map(([severity, count]) => (
                    <div key={severity} className="d-flex justify-content-between mt-1">
                      <Badge className={`${getSeverityClass(severity)} me-2`}>
                        {severity}
                      </Badge>
                      <span className="fw-bold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Orta Panel - CVE Listesi */}
        <Col md={5}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-warning text-dark d-flex justify-content-between align-items-center">
              <h5 className="mb-0"><FaShieldAlt className="me-2" />CVE Listesi</h5>
              <Badge bg="dark">{filteredCVEs.length} CVE</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {loading ? (
                <div className="text-center p-5">
                  <Spinner animation="border" />
                  <p className="mt-3">CVE verileri yükleniyor...</p>
                </div>
              ) : filteredCVEs.length === 0 ? (
                <div className="text-center p-5 text-muted">
                  <FaShieldAlt size={48} className="mb-3" />
                  <p>{cves.length === 0
                    ? <>CVE listesi boş.<br />"CVE Zafiyetlerini Getir" butonuna basın.</>
                    : <>Bu filtre ile eşleşen CVE bulunamadı.</>
                  }</p>
                </div>
              ) : (
                <div className="list-group list-group-flush">
                  {filteredCVEs.map((item, index) => (
                    <div
                      key={index}
                      className={`list-group-item cve-item p-3 ${selectedCVE === item ? 'active' : ''}`}
                      onClick={() => setSelectedCVE(item)}
                    >
                      <div className="d-flex w-100 justify-content-between mb-2">
                        <span className={`source-badge source-${item.source.toLowerCase()}`}>
                          {getSourceIcon(item.source)}{item.source}
                        </span>
                        <small className="text-muted">{item.published_date}</small>
                      </div>
                      <h6 className="mb-1 fw-bold">{item.cve_id}</h6>
                      <div className="d-flex justify-content-between align-items-center mt-2">
                        <Badge className={getSeverityClass(item.severity)}>
                          <FaExclamationTriangle className="me-1" />
                          {item.severity}
                        </Badge>
                        {item.cvss_score && (
                          <span className={`cvss-score ${getCVSSClass(item.cvss_score)}`}>
                            CVSS: {item.cvss_score}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Sağ Panel - CVE Detayları */}
        <Col md={4}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0"><FaShieldAlt className="me-2" />CVE Detayları</h5>
            </Card.Header>
            <Card.Body>
              {!selectedCVE ? (
                <div className="text-center p-5 text-muted">
                  <FaShieldAlt size={48} className="mb-3" />
                  <p>Detayları görmek için<br />listeden bir CVE seçin.</p>
                </div>
              ) : (
                <div className="fade-in">
                  <div
                    className="p-2 text-white mb-3 rounded d-flex justify-content-between align-items-center"
                    style={{ backgroundColor: getSourceColor(selectedCVE.source) }}
                  >
                    <small>
                      {getSourceIcon(selectedCVE.source)}{selectedCVE.source}
                    </small>
                    <small>{selectedCVE.published_date}</small>
                  </div>

                  <div className="d-flex justify-content-between align-items-start mb-3">
                    <h5 className="fw-bold">{selectedCVE.cve_id}</h5>
                    <Badge className={getSeverityClass(selectedCVE.severity)}>
                      {selectedCVE.severity}
                    </Badge>
                  </div>

                  {selectedCVE.cvss_score && (
                    <div className="mb-3">
                      <span className={`cvss-score ${getCVSSClass(selectedCVE.cvss_score)}`}>
                        CVSS Skoru: {selectedCVE.cvss_score} / 10
                      </span>
                    </div>
                  )}

                  <div className="mb-3">
                    <h6 className="fw-bold text-danger">Başlık</h6>
                    <div className="p-2 bg-light rounded">
                      {selectedCVE.turkish_title || selectedCVE.original_title}
                    </div>
                  </div>

                  <div className="mb-3">
                    <h6 className="fw-bold text-danger">Açıklama</h6>
                    <div className="article-content p-3 bg-light rounded">
                      {(selectedCVE.turkish_description || selectedCVE.original_description) ? (
                        (selectedCVE.turkish_description || selectedCVE.original_description)
                          .split('\n\n').map((paragraph, idx) => (
                            <p key={idx} className="mb-2" style={{ lineHeight: '1.7', textAlign: 'justify' }}>
                              {paragraph}
                            </p>
                          ))
                      ) : (
                        <p className="text-muted">İçerik bulunmuyor.</p>
                      )}
                    </div>
                  </div>

                  {selectedCVE.cwe_ids && selectedCVE.cwe_ids.length > 0 && (
                    <div className="mb-3">
                      <h6 className="fw-bold text-danger">CWE ID'leri</h6>
                      <div>
                        {selectedCVE.cwe_ids.map((cwe, idx) => (
                          <Badge key={idx} bg="secondary" className="me-1">
                            {cwe}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedCVE.affected_products && (
                    <div className="mb-3">
                      <h6 className="fw-bold text-danger">Etkilenen Ürünler</h6>
                      <div className="p-2 bg-light rounded">
                        {selectedCVE.affected_products}
                      </div>
                    </div>
                  )}

                  {selectedCVE.references && selectedCVE.references.length > 0 && (
                    <div className="mb-3">
                      <h6 className="fw-bold text-danger">Referanslar</h6>
                      <ul className="list-unstyled">
                        {selectedCVE.references.slice(0, 3).map((ref, idx) => (
                          <li key={idx} className="mb-1">
                            <a href={ref} target="_blank" rel="noopener noreferrer" className="small">
                              <FaExternalLinkAlt className="me-1" />
                              {ref.length > 50 ? ref.substring(0, 50) + '...' : ref}
                            </a>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <a
                    href={selectedCVE.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-outline-danger btn-sm"
                  >
                    <FaExternalLinkAlt className="me-2" />Orijinal Kaynağa Git
                  </a>
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>

      {/* Loading Modal */}
      <Modal show={fetching} backdrop="static" keyboard={false} centered>
        <Modal.Body className="text-center p-5">
          <Spinner animation="border" variant="danger" style={{ width: '3rem', height: '3rem' }} />
          <h5 className="mt-3">CVE Verileri Getiriliyor...</h5>
          <p className="text-muted mb-0">Lütfen bekleyin, bu işlem biraz zaman alabilir.</p>
        </Modal.Body>
      </Modal>

      {/* Error Alert */}
      {error && (
        <Alert
          variant="danger"
          className="position-fixed top-0 end-0 m-3"
          style={{ zIndex: 9999, minWidth: '300px' }}
          dismissible
          onClose={() => setError(null)}
        >
          {error}
        </Alert>
      )}
    </Container>
  )
}

export default CVEComponent