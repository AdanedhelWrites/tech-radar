import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import { Alert } from 'react-bootstrap'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { kacis, guvenliHref } from '../utils/html'
import BolumSayfasi, { BolumCubugu } from './bolum/BolumSayfasi'
import { FaCalendarWeek, FaInfoCircle, FaBell, FaGoogle, FaCode } from 'react-icons/fa'
import { sreApi, istekHataMesaji } from '../services/api'

// SRE sayfasi (spec 2026-10-31 G4): gorunum bolum/BolumSayfasi'nda, veri ve eylemler burada.

const sources = [
  { id: 'sre_source1', name: 'SRE Weekly', value: 'SRE Weekly', icon: FaCalendarWeek },
  { id: 'sre_source2', name: 'InfoQ SRE', value: 'InfoQ SRE', icon: FaInfoCircle },
  { id: 'sre_source3', name: 'PagerDuty Eng', value: 'PagerDuty Eng', icon: FaBell },
  { id: 'sre_source4', name: 'Google Cloud SRE', value: 'Google Cloud SRE', icon: FaGoogle },
  { id: 'sre_source5', name: 'DZone DevOps', value: 'DZone DevOps', icon: FaCode },
]

const GUN_SECENEKLERI = Array.from({ length: 15 }, (_, i) => i + 1)

function SREComponent() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [stats, setStats] = useState({
    total: 0,
    by_source: {},
    last_update: null
  })
  const [days, setDays] = useState(7)
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
      const response = await sreApi.getSRE()
      if (response.data.success) {
        setEntries(response.data.data)
      }
    } catch (err) {
      if (!silent) setError('SRE haberleri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await sreApi.getStats()
      if (response.data.success) {
        setStats(response.data)
      }
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }

  const handleFetchSRE = async () => {
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

      const response = await sreApi.fetchSRE({
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
      setError(istekHataMesaji(err, 'SRE haberleri getirilirken hata oluştu'))
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm SRE haberleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await sreApi.clearCache()
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
      const response = await sreApi.exportSRE()
      if (response.data.success) {
        const items = response.data.data
        const date = new Date().toLocaleDateString('tr-TR')
        const html = `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>SRE Raporu - ${date}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: #5b86a7; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .article .source { display: inline-block; background: #5b86a7; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc; }
  .article a { color: #5b86a7; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
  @media print { body { background: #fff; color: #000; } .article { border-color: #ddd; background: #f9f9f9; } .article h3, .article .content { color: #000; } h1 { color: #333; } }
</style>
</head>
<body>
<h1>SRE Haberleri Raporu</h1>
<p class="meta">${date} tarihinde oluşturuldu &mdash; ${items.length} haber</p>
${items.map(item => {
          const content = (item.turkish_description || item.original_description || '').replace(/\n/g, '<br>')
          return `<div class="article">
  <span class="source">${kacis(item.source || '')}</span><span class="date">${kacis(item.published_date || '')}</span>
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
        a.download = `sre_raporu_${new Date().toISOString().split('T')[0]}.html`
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
        bolum="sre"
        baslik="SRE"
        kayitlar={entries}
        yukleniyor={loading}
        istatistik={stats}
        cubuk={
          <BolumCubugu
            kimlik="sre"
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
            onCek={handleFetchSRE}
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

export default SREComponent
