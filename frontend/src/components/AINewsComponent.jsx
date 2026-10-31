import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import { Alert } from 'react-bootstrap'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { kacis, guvenliHref } from '../utils/html'
import BolumSayfasi, { BolumCubugu } from './bolum/BolumSayfasi'
import { FaRobot, FaMicrochip, FaNewspaper, FaEnvelope } from 'react-icons/fa'
import { aiApi, istekHataMesaji } from '../services/api'

// Yapay Zeka sayfasi (spec 2026-10-31 G4): gorunum bolum/BolumSayfasi'nda, veri ve eylemler burada.

const sources = [
  { id: 'ai_source1', name: 'Hugging Face', value: 'Hugging Face', icon: FaRobot },
  { id: 'ai_source2', name: 'MIT Tech Review AI', value: 'MIT Tech Review AI', icon: FaMicrochip },
  { id: 'ai_source3', name: 'MarkTechPost', value: 'MarkTechPost', icon: FaMicrochip },
  { id: 'ai_source4', name: 'AWS ML Blog', value: 'AWS ML Blog', icon: FaRobot },
  { id: 'ai_source5', name: 'TechCrunch AI', value: 'TechCrunch AI', icon: FaMicrochip },
  { id: 'ai_source6', name: 'Google DeepMind', value: 'Google DeepMind', icon: FaRobot },
  { id: 'ai_source8', name: 'OpenAI Blog', value: 'OpenAI Blog', icon: FaRobot },
  // 2026-10-14: KDnuggets (403) yerine; value arka uctaki kaynak adiyla birebir (news/ai_scraper.py)
  { id: 'ai_source9', name: 'Ars Technica AI', value: 'Ars Technica AI', icon: FaNewspaper },
  { id: 'ai_source10', name: 'Import AI', value: 'Import AI', icon: FaEnvelope },
]

const GUN_SECENEKLERI = [1, 3, 7, 14, 21, 30, 45, 60]

function AINewsComponent() {
  const [entries, setEntries] = useState([])
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

  // Sekme arka plandayken durur (hooks/useAraliklaYenile)
  useAraliklaYenile(() => loadEntries(true), 5000)

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
        loadStats()
        toast.success("Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError(istekHataMesaji(err, 'AI haberleri getirilirken hata oluştu'))
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm AI güncellemeleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await aiApi.clearCache()
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
  <span class="source">${kacis(item.source || '')}</span><span class="date">${kacis(item.published_date || '')}</span>
  <h3>${kacis(item.turkish_title || item.original_title || '')}</h3>
  <div class="content">${content}</div>
  <a href="${guvenliHref(item.link)}" target="_blank">Kaynağa Git &rarr;</a>
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

  return (
    <>
      <BolumSayfasi
        bolum="ai"
        baslik="Yapay Zeka"
        kayitlar={entries}
        yukleniyor={loading}
        istatistik={stats}
        cubuk={
          <BolumCubugu
            kimlik="ai"
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
            onCek={handleFetchAINews}
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

export default AINewsComponent
