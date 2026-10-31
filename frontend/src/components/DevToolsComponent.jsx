import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import { Alert } from 'react-bootstrap'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { kacis, guvenliHref } from '../utils/html'
import { KAYIT_TURU } from '../utils/okumaKaydi'
import BolumSayfasi, { BolumCubugu } from './bolum/BolumSayfasi'
import { FaDatabase, FaStream, FaHdd, FaLeaf, FaEnvelope, FaSearch, FaBolt, FaGraduationCap,
  FaRobot, FaProjectDiagram, FaChartLine, FaGitlab, FaKey } from 'react-icons/fa'
import { devtoolsApi, istekHataMesaji } from '../services/api'

// DevTools sayfasi (spec 2026-10-31 G4): gorunum bolum/BolumSayfasi'nda, veri ve eylemler burada.
// Surum ve kayit turu (release/blog/news) satirda ve panelde bilgi rozeti; tur dagilimi baslikta.

const sources = [
  // 2026-10-14: MinIO cikarildi (ust kaynak Ekim 2025'ten beri surum yayinlamiyor)
  { id: 'dt_source2', name: 'Seq', value: 'Seq', icon: FaStream },
  { id: 'dt_source3', name: 'Ceph', value: 'Ceph', icon: FaHdd },
  { id: 'dt_source4', name: 'MongoDB', value: 'MongoDB', icon: FaLeaf },
  { id: 'dt_source5', name: 'PostgreSQL', value: 'PostgreSQL', icon: FaDatabase },
  { id: 'dt_source6', name: 'RabbitMQ', value: 'RabbitMQ', icon: FaEnvelope },
  { id: 'dt_source7', name: 'Elastic', value: 'Elastic', icon: FaSearch },
  { id: 'dt_source8', name: 'Redis', value: 'Redis', icon: FaBolt },
  { id: 'dt_source9', name: 'Moodle', value: 'Moodle', icon: FaGraduationCap },
  { id: 'dt_source10', name: 'LiteLLM', value: 'LiteLLM', icon: FaRobot },
  { id: 'dt_source11', name: 'LangGraph', value: 'LangGraph', icon: FaProjectDiagram },
  { id: 'dt_source12', name: 'Langfuse', value: 'Langfuse', icon: FaChartLine },
  { id: 'dt_source13', name: 'GitLab', value: 'GitLab', icon: FaGitlab },
  { id: 'dt_source14', name: 'Keycloak', value: 'Keycloak', icon: FaKey },
]

const GUN_SECENEKLERI = [1, 3, 7, 14, 21, 30, 45, 60]

function DevToolsComponent() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({
    total: 0,
    by_source: {},
    by_type: {},
    last_update: null
  })
  const [days, setDays] = useState(30)
  const [selectedSources, setSelectedSources] = useState(
    sources.reduce((acc, s) => ({ ...acc, [s.value]: true }), {})
  )

  // Sekme arka plandayken durur (hooks/useAraliklaYenile)
  useAraliklaYenile(() => loadEntries(true), 5000)

  useEffect(() => {
    loadEntries()
    loadStats()
  }, [])

  const loadEntries = async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      const response = await devtoolsApi.getDevTools()
      if (response.data.success) {
        setEntries(response.data.data)
      }
    } catch (err) {
      if (!silent) setError('DevTools güncellemeleri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await devtoolsApi.getStats()
      if (response.data.success) {
        setStats(response.data)
      }
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }

  const handleFetchDevTools = async () => {
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

      const response = await devtoolsApi.fetchDevTools({
        days: parseInt(days),
        sources: activeSources
      })

      if (response.data.success) {
        loadStats()
        toast.success("Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError(istekHataMesaji(err, 'DevTools güncellemeleri getirilirken hata oluştu'))
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm DevTools güncellemeleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await devtoolsApi.clearCache()
      // Liste bosalinca acik kayit cozulemez, panel kendiliginden kapanir
      setEntries([])
      loadStats()
      toast.success("Veriler başarıyla temizlendi", { icon: "🗑️" })
    } catch (err) {
      setError(err.response?.status === 403
        ? 'Sıfırlama için yönetici girişi gerekli: önce Django admin (/admin) üzerinden oturum açın.'
        : 'Sıfırlama sırasında hata oluştu')
    }
  }

  const handleExport = async () => {
    try {
      const response = await devtoolsApi.exportDevTools()
      if (response.data.success) {
        const items = response.data.data
        const date = new Date().toLocaleDateString('tr-TR')
        const html = `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>DevTools Raporu - ${date}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: #5b86a7; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .article .source { display: inline-block; background: #5b86a7; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .version { display: inline-block; background: #2ecc71; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc; }
  .article a { color: #5b86a7; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
  @media print { body { background: #fff; color: #000; } .article { border-color: #ddd; background: #f9f9f9; } .article h3, .article .content { color: #000; } h1 { color: #333; } }
</style>
</head>
<body>
<h1>DevTools Güncellemeleri Raporu</h1>
<p class="meta">${date} tarihinde oluşturuldu &mdash; ${items.length} güncelleme</p>
${items.map(item => {
          const content = (item.turkish_description || item.original_description || '').replace(/\n/g, '<br>')
          const versionBadge = item.version ? `<span class="version">${kacis(item.version)}</span>` : ''
          return `<div class="article">
  <span class="source">${kacis(item.source || '')}</span>${versionBadge}<span class="date">${kacis(item.published_date || '')}</span>
  <h3>${kacis(item.turkish_title || item.original_title || '')}</h3>
  <div class="content">${content}</div>
  <a href="${guvenliHref(item.link)}" target="_blank">Kaynağa Git &rarr;</a>
</div>`
        }).join('\n')}
</body></html>`
        const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `devtools_raporu_${new Date().toISOString().split('T')[0]}.html`
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

  const turDagilimi = Object.entries(stats.by_type || {}).map(([tur, count]) => [KAYIT_TURU[tur] || tur, count])

  return (
    <>
      <BolumSayfasi
        bolum="devtools"
        baslik="DevTools"
        kayitlar={entries}
        yukleniyor={loading}
        istatistik={stats}
        dagilim={turDagilimi}
        cubuk={
          <BolumCubugu
            kimlik="devtools"
            gun={days}
            gunSecenekleri={GUN_SECENEKLERI}
            onGunDegis={setDays}
            kaynaklar={sources}
            seciliKaynaklar={selectedSources}
            onKaynakDegis={toggleSource}
            kaynakSayilari={stats.by_source}
            yukleniyor={loading}
            cekiliyor={fetching}
            onYenile={() => loadEntries()}
            onRapor={handleExport}
            onTemizle={handleClearCache}
            onCek={handleFetchDevTools}
          />
        }
      />

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
    </>
  )
}

export default DevToolsComponent
