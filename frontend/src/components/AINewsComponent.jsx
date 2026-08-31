import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import {
  Container, Row, Col, Card, Button, Form,
  Badge, Spinner, Alert, Modal
} from 'react-bootstrap'
import {
  FaDownload, FaSync, FaTrash, FaFileExport,
  FaChartBar, FaCogs, FaExternalLinkAlt,
  FaRobot, FaMicrochip
} from 'react-icons/fa'
import { aiApi } from '../services/api'

const sources = [
  { id: 'ai_source1', name: 'Hugging Face', value: 'Hugging Face', icon: FaRobot, color: '#ffb300' },
  { id: 'ai_source2', name: 'AI News', value: 'AI News', icon: FaMicrochip, color: '#0052cc' },
  { id: 'ai_source3', name: 'MarkTechPost', value: 'MarkTechPost', icon: FaMicrochip, color: '#e74c3c' },
  { id: 'ai_source4', name: 'AWS ML Blog', value: 'AWS ML Blog', icon: FaRobot, color: '#f39c12' },
  { id: 'ai_source5', name: 'TechCrunch AI', value: 'TechCrunch AI', icon: FaMicrochip, color: '#00a562' },
  { id: 'ai_source6', name: 'Google DeepMind', value: 'Google DeepMind', icon: FaRobot, color: '#4285f4' },
  { id: 'ai_source7', name: 'KDnuggets', value: 'KDnuggets', icon: FaMicrochip, color: '#f1c40f' },
  { id: 'ai_source8', name: 'OpenAI Blog', value: 'OpenAI Blog', icon: FaRobot, color: '#10a37f' },
]

function AINewsComponent() {
  const [entries, setEntries] = useState([])
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({
    total: 0,
    by_source: {},
    last_update: null
  })
  const [days, setDays] = useState(30)
  const [selectedSources, setSelectedSources] = useState(
    sources.reduce((acc, s) => ({ ...acc, [s.value]: true }), {})
  )

  useEffect(() => {
    const interval = setInterval(() => {
      loadEntries(true)
    }, 5000)
    return () => clearInterval(interval)
  }, [])


  useEffect(() => {
    loadEntries()
    loadStats()
  }, [])

  const loadEntries = async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      const response = await aiApi.getAINews()
      if (response.data.success) {
        setEntries(response.data.data)
      }
    } catch (err) {
      if (!silent) setError('AI güncellemeleri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await aiApi.getStats()
      if (response.data.success) {
        setStats(response.data)
      }
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }

  const handleFetchAINews = async () => {
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

      const response = await aiApi.fetchAINews({
        days: parseInt(days),
        sources: activeSources
      })

      if (response.data.success) {
        setEntries(response.data.data)
        loadStats()
        toast.success("Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError('AI haberleri getirilirken hata oluştu: ' + err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm AI güncellemeleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await aiApi.clearCache()
      setEntries([])
      setSelectedEntry(null)
      loadStats()
      toast.success("Veriler başarıyla temizlendi", { icon: "🗑️" })
    } catch (err) {
      setError('Sıfırlama sırasında hata oluştu')
    }
  }

  const handleExport = async () => {
    try {
      const response = await aiApi.exportAINews()
      if (response.data.success) {
        const items = response.data.data
        const date = new Date().toLocaleDateString('tr-TR')
        const html = `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Yapay Zeka (AI) Raporu - ${date}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: #8e44ad; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .article .source { display: inline-block; background: #8e44ad; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc; }
  .article a { color: #8e44ad; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>Yapay Zeka Güncellemeleri Raporu</h1>
<p class="meta">${date} tarihinde oluşturuldu &mdash; ${items.length} güncelleme</p>
${items.map(item => {
          const content = (item.turkish_description || item.original_description || '').replace(/\\n/g, '<br>')
          return `<div class="article">
  <span class="source">${item.source || ''}</span><span class="date">${item.published_date || ''}</span>
  <h3>${item.turkish_title || item.original_title || ''}</h3>
  <div class="content">${content}</div>
  <a href="${item.link || ''}" target="_blank">Kaynağa Git &rarr;</a>
</div>`
        }).join('\\n')}
</body></html>`
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `ai_haberleri_raporu_${new Date().toISOString().split('T')[0]}.html`
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

  const getSourceIcon = (sourceName) => {
    const found = sources.find(s => s.value === sourceName)
    if (found) {
      const IconComp = found.icon
      return <IconComp className="me-1" size={12} />
    }
    return <FaRobot className="me-1" size={12} />
  }

  const getSourceColor = (sourceName) => {
    const found = sources.find(s => s.value === sourceName)
    return found ? found.color : '#8e44ad'
  }

  return (
    <Container fluid>
      <Row>
        {/* Sol Panel - Kontroller */}
        <Col md={3}>
          <Card className="mb-4">
            <Card.Header className="bg-primary text-white">
              <h5 className="mb-0"><FaCogs className="me-2" />Kontroller</h5>
            </Card.Header>
            <Card.Body>
              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">Kaç Günlük Haber?</Form.Label>
                <Form.Range
                  min={1}
                  max={60}
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                />
                <div className="text-center">
                  <Badge bg="secondary" className="fs-6">{days} Gün</Badge>
                </div>
              </Form.Group>

              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">Yapay Zeka Kaynakları</Form.Label>
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

              <Button
                variant="primary"
                className="w-100 mb-2"
                onClick={handleFetchAINews}
                disabled={fetching}
              >
                {fetching ? (
                  <><Spinner size="sm" className="me-2" />Getiriliyor...</>
                ) : (
                  <><FaDownload className="me-2" />Haberleri Getir</>
                )}
              </Button>

              <Button
                variant="outline-secondary"
                className="w-100 mb-2"
                onClick={() => loadEntries()}
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
                  title="Tüm AI haberlerini sil ve sıfırla"
                >
                  <FaTrash className="me-1" />Sıfırla
                </Button>

                <Button
                  variant="outline-warning"
                  className="flex-fill"
                  size="sm"
                  onClick={handleExport}
                  title="AI haberlerini HTML rapor olarak indir"
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
                  <span>Toplam Güncelleme:</span>
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
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Orta Panel - Güncelleme Listesi */}
        <Col md={5}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-info text-white d-flex justify-content-between align-items-center">
              <h5 className="mb-0"><FaRobot className="me-2" />Yapay Zeka (AI) Gelişmeleri</h5>
              <Badge bg="light" text="dark">{entries.length} haber</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {loading ? (
                <div className="text-center p-5">
                  <Spinner animation="border" />
                  <p className="mt-3">AI gelişmeleri yükleniyor...</p>
                </div>
              ) : entries.length === 0 ? (
                <div className="text-center p-5 text-muted">
                  <FaRobot size={48} className="mb-3" />
                  <p>Liste boş.<br />"Haberleri Getir" butonuna basın.</p>
                </div>
              ) : (
                <div className="list-group list-group-flush">
                  {entries.map((item, index) => (
                    <div
                      key={index}
                      className={`list-group-item news-item p-3 ${selectedEntry === item ? 'active' : ''}`}
                      onClick={() => setSelectedEntry(item)}
                    >
                      <div className="d-flex w-100 justify-content-between mb-2">
                        <div className="d-flex align-items-center gap-1">
                          <span
                            className="badge rounded-pill text-white"
                            style={{ backgroundColor: getSourceColor(item.source) }}
                          >
                            {getSourceIcon(item.source)}{item.source}
                          </span>
                        </div>
                        <small className="text-muted">{item.published_date}</small>
                      </div>
                      <h6 className="mb-1 fw-bold">
                        {item.turkish_title?.length > 80
                          ? item.turkish_title.substring(0, 80) + '...'
                          : item.turkish_title || item.original_title}
                      </h6>
                    </div>
                  ))}
                </div>
              )}
            </Card.Body>
          </Card>
        </Col>

        {/* Sag Panel - Detaylar */}
        <Col md={4}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0"><FaRobot className="me-2" />Gelişme Detayları</h5>
            </Card.Header>
            <Card.Body>
              {!selectedEntry ? (
                <div className="text-center p-5 text-muted">
                  <FaRobot size={48} className="mb-3" />
                  <p>Detayları görmek için<br />listeden bir haber seçin.</p>
                </div>
              ) : (
                <div className="fade-in">
                  <div
                    className="p-2 text-white mb-3 rounded d-flex justify-content-between align-items-center"
                    style={{ backgroundColor: getSourceColor(selectedEntry.source) }}
                  >
                    <small><FaRobot className="me-2" />{selectedEntry.source}</small>
                    <small>{selectedEntry.published_date}</small>
                  </div>

                  <h5 className="fw-bold mb-3">
                    {selectedEntry.turkish_title || selectedEntry.original_title}
                  </h5>

                  <div className="mb-3 article-content p-3 bg-light rounded">
                    {selectedEntry.turkish_description ? (
                      selectedEntry.turkish_description.split('\\n\\n').map((paragraph, idx) => (
                        <p key={idx} className="mb-2" style={{ lineHeight: '1.7', textAlign: 'justify' }}>
                          {paragraph}
                        </p>
                      ))
                    ) : (
                      <p className="text-muted">İçerik bulunmuyor.</p>
                    )}
                  </div>

                  <a
                    href={selectedEntry.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-outline-primary btn-sm"
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
          <Spinner animation="border" variant="primary" style={{ width: '3rem', height: '3rem' }} />
          <h5 className="mt-3">Yapay Zeka (AI) Gelişmeleri Getiriliyor...</h5>
          <p className="text-muted mb-0">Lütfen bekleyin, API/Scraping ve çeviri süreci biraz zaman alabilir.</p>
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

export default AINewsComponent
