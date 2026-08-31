import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import {
  Container, Row, Col, Card, Button, Form,
  Badge, Spinner, Alert, Modal
} from 'react-bootstrap'
import {
  FaDownload, FaSync, FaTrash, FaFileExport,
  FaDharmachakra, FaChartBar, FaCogs,
  FaExternalLinkAlt, FaTag, FaCodeBranch,
  FaGithub, FaCloud, FaBug, FaStar, FaCode
} from 'react-icons/fa'
import { k8sApi } from '../services/api'

const sources = [
  { id: 'k8s_source1', name: 'K8s Blog', value: 'K8s Blog', icon: FaDharmachakra, color: '#326ce5' },
  { id: 'k8s_source2', name: 'GitHub Releases', value: 'GitHub Releases', icon: FaGithub, color: '#24292e' },
  { id: 'k8s_source3', name: 'CNCF Blog', value: 'CNCF Blog', icon: FaCloud, color: '#00aec7' },
]

const categoryLabels = {
  release: 'Sürüm',
  security: 'Güvenlik',
  feature: 'Özellik',
  ecosystem: 'Ekosistem',
  blog: 'Blog',
}

function KubernetesComponent() {
  const [entries, setEntries] = useState([])
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({
    total: 0,
    by_source: {},
    by_category: {},
    last_update: null
  })
  const [days, setDays] = useState(7)
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
      const response = await k8sApi.getK8s()
      if (response.data.success) {
        setEntries(response.data.data)
      }
    } catch (err) {
      if (!silent) setError('Kubernetes haberleri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await k8sApi.getStats()
      if (response.data.success) {
        setStats(response.data)
      }
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }

  const handleFetchK8s = async () => {
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


      const response = await k8sApi.fetchK8s({
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
      setError('Kubernetes haberleri getirilirken hata oluştu: ' + err.message)
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm Kubernetes haberleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await k8sApi.clearCache()
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
      const response = await k8sApi.exportK8s()
      if (response.data.success) {
        const items = response.data.data
        const date = new Date().toLocaleDateString('tr-TR')
        const html = `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>Kubernetes Raporu - ${date}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: #5b86a7; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .article .source { display: inline-block; background: #326ce5; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .version { display: inline-block; background: #1a1a24; color: #5b86a7; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-family: monospace; margin-right: 0.5rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc; white-space: pre-wrap; }
  .article a { color: #5b86a7; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
  @media print { body { background: #fff; color: #000; } .article { border-color: #ddd; background: #f9f9f9; } .article h3, .article .content { color: #000; } h1 { color: #333; } }
</style>
</head>
<body>
<h1>Kubernetes Haberleri Raporu</h1>
<p class="meta">${date} tarihinde oluşturuldu &mdash; ${items.length} haber</p>
${items.map(item => {
          const content = (item.turkish_description || item.original_description || '').replace(/\n/g, '<br>')
          return `<div class="article">
  <span class="source">${item.source || ''}</span>${item.version ? `<span class="version">${item.version}</span>` : ''}<span class="date">${item.published_date || ''}</span>
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
        a.download = `kubernetes_raporu_${new Date().toISOString().split('T')[0]}.html`
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

  const getCategoryClass = (category) => {
    return `category-${category || 'blog'}`
  }

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

  const getSourceClass = (source) => {
    const sourceMap = {
      'K8s Blog': 'source-k8s-blog',
      'GitHub Releases': 'source-github-releases',
      'CNCF Blog': 'source-cncf-blog',
    }
    return sourceMap[source] || 'bg-secondary'
  }

  const sectionIcons = {
    'Hata veya Gerileme': FaBug,
    'Özellik': FaStar,
    'Bağımlılıklar': FaCode,
    'Acil Yükseltme Notları': FaExternalLinkAlt,
  }

  const sectionColors = {
    'Hata veya Gerileme': '#dc3545',
    'Özellik': '#28a745',
    'Bağımlılıklar': '#6f42c1',
    'Acil Yükseltme Notları': '#fd7e14',
  }

  /** Yapısal CHANGELOG formatını zengin JSX olarak render eder */
  const renderStructuredContent = (text) => {
    const lines = text.split('\n')
    const elements = []
    let currentItems = []
    let currentSection = null
    let itemDesc = null
    let itemPR = null
    let key = 0

    const flushItem = () => {
      if (!itemDesc) return
      const desc = itemDesc
      const pr = itemPR
      currentItems.push(
        <li key={key++} className="changelog-item mb-3">
          <div className="changelog-desc" style={{ lineHeight: '1.6' }}>
            {desc.split(/(`[^`]+`)/).map((part, i) => {
              if (part.startsWith('`') && part.endsWith('`')) {
                return <code key={i} className="changelog-code">{part.slice(1, -1)}</code>
              }
              return <span key={i}>{part}</span>
            })}
          </div>
          {pr && (
            <div className="changelog-meta mt-1">
              <a
                href={`https://github.com/kubernetes/kubernetes/pull/${pr.num}`}
                target="_blank"
                rel="noopener noreferrer"
                className="changelog-pr-link me-2"
              >
                <FaCodeBranch size={10} className="me-1" />#{pr.num}
              </a>
              <span className="changelog-author me-2">@{pr.author}</span>
              {pr.sigs.split(',').map((sig, i) => (
                <Badge key={i} bg="none" className="changelog-sig-badge me-1">
                  {sig.trim()}
                </Badge>
              ))}
            </div>
          )}
        </li>
      )
      itemDesc = null
      itemPR = null
    }

    const flushSection = () => {
      flushItem()
      if (currentItems.length > 0 && currentSection) {
        const SIcon = sectionIcons[currentSection] || FaTag
        const sColor = sectionColors[currentSection] || '#6c757d'
        elements.push(
          <div key={key++} className="changelog-section mb-3">
            <h6 className="changelog-section-header" style={{ borderLeftColor: sColor }}>
              <SIcon className="me-2" style={{ color: sColor }} size={14} />
              {currentSection}
              <Badge bg="none" className="ms-2 changelog-count-badge">{currentItems.length}</Badge>
            </h6>
            <ul className="changelog-list">
              {currentItems}
            </ul>
          </div>
        )
      }
      currentItems = []
    }

    for (const line of lines) {
      const trimmed = line.trim()

      // Section başlığı
      const sectionMatch = trimmed.match(/^===SECTION:\s*(.+)===$/)
      if (sectionMatch) {
        flushSection()
        currentSection = sectionMatch[1].trim()
        continue
      }

      // Item ayırıcı
      if (trimmed === '---ITEM---') {
        flushItem()
        continue
      }

      // PR referansı
      const prMatch = trimmed.match(/^<<<PR#(\d+)\|@([\w-]+)\|(.+)>>>$/)
      if (prMatch) {
        itemPR = { num: prMatch[1], author: prMatch[2], sigs: prMatch[3] }
        continue
      }

      // Açıklama metni
      if (trimmed) {
        itemDesc = itemDesc ? itemDesc + ' ' + trimmed : trimmed
      }
    }
    flushSection()

    return elements.length > 0 ? elements : null
  }

  /** İçerik GitHub yapısal mı yoksa normal blog metni mi? */
  const renderDetailContent = (entry) => {
    const content = entry.turkish_description || entry.original_description || ''

    // GitHub Releases yapısal format
    if (entry.source === 'GitHub Releases' && content.includes('===SECTION:')) {
      const structured = renderStructuredContent(content)
      if (structured) {
        return <div className="changelog-content">{structured}</div>
      }
    }

    // Normal blog/haber içeriği
    if (content) {
      return content.split('\n\n').map((paragraph, idx) => (
        <p key={idx} className="mb-2" style={{ lineHeight: '1.7', textAlign: 'justify' }}>
          {paragraph}
        </p>
      ))
    }

    return <p className="text-muted">İçerik bulunmuyor.</p>
  }

  return (
    <Container fluid>
      <Row>
        {/* Sol Panel - Kontroller */}
        <Col md={3}>
          <Card className="mb-4">
            <Card.Header className="bg-info text-white">
              <h5 className="mb-0"><FaCogs className="me-2" />Kontroller</h5>
            </Card.Header>
            <Card.Body>
              <Form.Group className="mb-4">
                <Form.Label className="fw-bold">Kaç Günlük Haber?</Form.Label>
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
                <Form.Label className="fw-bold">Kaynaklar</Form.Label>
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
                variant="info"
                className="w-100 mb-2 text-white"
                onClick={handleFetchK8s}
                disabled={fetching}
              >
                {fetching ? (
                  <><Spinner size="sm" className="me-2" />Getiriliyor...</>
                ) : (
                  <><FaDownload className="me-2" />Kubernetes Haberlerini Getir</>
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
                  title="Tüm K8s haberlerini sil ve sıfırla"
                >
                  <FaTrash className="me-1" />Sıfırla
                </Button>

                <Button
                  variant="outline-warning"
                  className="flex-fill"
                  size="sm"
                  onClick={handleExport}
                  title="Kubernetes haberlerini HTML rapor olarak indir"
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
                  <span>Toplam Haber:</span>
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
                  {Object.entries(stats.by_source || {}).map(([source, count]) => (
                    <div key={source} className="d-flex justify-content-between mt-1">
                      <span>{source}:</span>
                      <span className="fw-bold">{count}</span>
                    </div>
                  ))}
                </div>

                <div className="mt-3">
                  <small><strong>Kategoriler:</strong></small><br />
                  {Object.entries(stats.by_category || {}).map(([cat, count]) => (
                    <div key={cat} className="d-flex justify-content-between mt-1">
                      <Badge className={getCategoryClass(cat)}>
                        {categoryLabels[cat] || cat}
                      </Badge>
                      <span className="fw-bold">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>

        {/* Orta Panel - K8s Listesi */}
        <Col md={5}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-primary text-white d-flex justify-content-between align-items-center">
              <h5 className="mb-0"><FaDharmachakra className="me-2" />Kubernetes Haberleri</h5>
              <Badge bg="light" text="dark">{entries.length} Haber</Badge>
            </Card.Header>
            <Card.Body className="p-0">
              {loading ? (
                <div className="text-center p-5">
                  <Spinner animation="border" />
                  <p className="mt-3">Kubernetes haberleri yükleniyor...</p>
                </div>
              ) : entries.length === 0 ? (
                <div className="text-center p-5 text-muted">
                  <FaDharmachakra size={48} className="mb-3" />
                  <p>Kubernetes haber listesi boş.<br />"Kubernetes Haberlerini Getir" butonuna basın.</p>
                </div>
              ) : (
                <div className="list-group list-group-flush">
                  {entries.map((item, index) => (
                    <div
                      key={index}
                      className={`list-group-item k8s-item p-3 ${selectedEntry === item ? 'active' : ''}`}
                      onClick={() => setSelectedEntry(item)}
                    >
                      <div className="d-flex w-100 justify-content-between mb-2">
                        <span className={`source-badge ${getSourceClass(item.source)}`}>
                          {getSourceIcon(item.source)}{item.source}
                        </span>
                        <small className="text-muted">{item.published_date}</small>
                      </div>
                      <h6 className="mb-1 fw-bold">
                        {(item.turkish_title || item.original_title)?.length > 70
                          ? (item.turkish_title || item.original_title).substring(0, 70) + '...'
                          : (item.turkish_title || item.original_title)}
                      </h6>
                      <div className="d-flex justify-content-between align-items-center mt-2">
                        <Badge className={getCategoryClass(item.category)}>
                          {categoryLabels[item.category] || item.category}
                        </Badge>
                        {item.version && (
                          <span className="version-badge">
                            <FaTag className="me-1" />{item.version}
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

        {/* Sağ Panel - Detaylar */}
        <Col md={4}>
          <Card className="panel-card" style={{ height: 'calc(100vh - 150px)' }}>
            <Card.Header className="bg-secondary text-white">
              <h5 className="mb-0"><FaDharmachakra className="me-2" />Detaylar</h5>
            </Card.Header>
            <Card.Body>
              {!selectedEntry ? (
                <div className="text-center p-5 text-muted">
                  <FaDharmachakra size={48} className="mb-3" />
                  <p>Detayları görmek için<br />listeden bir haber seçin.</p>
                </div>
              ) : (
                <div className="fade-in">
                  <div
                    className="p-2 text-white mb-3 rounded d-flex justify-content-between align-items-center"
                    style={{ backgroundColor: getSourceColor(selectedEntry.source) }}
                  >
                    <small>
                      {getSourceIcon(selectedEntry.source)}{selectedEntry.source}
                    </small>
                    <small>{selectedEntry.published_date}</small>
                  </div>

                  <h5 className="fw-bold mb-3">
                    {selectedEntry.turkish_title || selectedEntry.original_title}
                  </h5>

                  <div className="mb-3 d-flex align-items-center gap-2">
                    <Badge className={getCategoryClass(selectedEntry.category)}>
                      {categoryLabels[selectedEntry.category] || selectedEntry.category}
                    </Badge>
                    {selectedEntry.version && (
                      <span className="version-badge">
                        <FaTag className="me-1" />{selectedEntry.version}
                      </span>
                    )}
                  </div>

                  <div className="mb-3 article-content p-3 bg-light rounded">
                    {renderDetailContent(selectedEntry)}
                  </div>

                  <a
                    href={selectedEntry.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-outline-info btn-sm"
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
          <Spinner animation="border" variant="info" style={{ width: '3rem', height: '3rem' }} />
          <h5 className="mt-3">Kubernetes Haberleri Getiriliyor...</h5>
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

export default KubernetesComponent