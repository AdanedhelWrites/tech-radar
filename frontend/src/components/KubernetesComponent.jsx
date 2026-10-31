import toast from 'react-hot-toast';
import { useState, useEffect } from 'react'
import { Alert } from 'react-bootstrap'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { kacis, guvenliHref } from '../utils/html'
import { KATEGORI } from '../utils/okumaKaydi'
import BolumSayfasi, { BolumCubugu } from './bolum/BolumSayfasi'
import { FaDharmachakra, FaGithub, FaCloud } from 'react-icons/fa'
import { k8sApi, istekHataMesaji } from '../services/api'

// Kubernetes sayfasi (spec 2026-10-31 G4): gorunum bolum/BolumSayfasi'nda, veri, eylemler ve
// kategori filtresi burada. Kategori etiketleri utils/okumaKaydi'daki tek kaynaktan gelir.
// GitHub Releases'in yapisal degisiklik gunlugu okuma panelinde okunur paragraflara cevrilir
// (utils/okumaKaydi degisiklikGunlugu).

const sources = [
  { id: 'k8s_source1', name: 'K8s Blog', value: 'K8s Blog', icon: FaDharmachakra },
  { id: 'k8s_source2', name: 'GitHub Releases', value: 'GitHub Releases', icon: FaGithub },
  { id: 'k8s_source3', name: 'CNCF Blog', value: 'CNCF Blog', icon: FaCloud },
]

const GUN_SECENEKLERI = Array.from({ length: 15 }, (_, i) => i + 1)
const KATEGORI_SECENEKLERI = [['all', 'Tümü'], ...Object.entries(KATEGORI)]

function KubernetesComponent() {
  const [entries, setEntries] = useState([])
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
  const [category, setCategory] = useState('all')

  // Sekme arka plandayken durur (hooks/useAraliklaYenile)
  useAraliklaYenile(() => loadEntries(true), 5000)

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
        loadStats()
        toast.success("Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError(istekHataMesaji(err, 'Kubernetes haberleri getirilirken hata oluştu'))
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm Kubernetes haberleri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await k8sApi.clearCache()
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
  <span class="source">${kacis(item.source || '')}</span>${item.version ? `<span class="version">${kacis(item.version)}</span>` : ''}<span class="date">${kacis(item.published_date || '')}</span>
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

  const kategoriDagilimi = Object.entries(stats.by_category || {}).map(([cat, count]) => [KATEGORI[cat] || cat, count])

  return (
    <>
      <BolumSayfasi
        bolum="kubernetes"
        baslik="Kubernetes"
        kayitlar={entries}
        yukleniyor={loading}
        istatistik={stats}
        dagilim={kategoriDagilimi}
        filtre={category === 'all' ? null : (k) => k.category === category}
        cubuk={
          <BolumCubugu
            kimlik="k8s"
            gun={days}
            gunSecenekleri={GUN_SECENEKLERI}
            onGunDegis={setDays}
            kaynaklar={sources}
            seciliKaynaklar={selectedSources}
            onKaynakDegis={toggleSource}
            kaynakSayilari={stats.by_source}
            ekFiltre={
              <div className="filtre-grubu siddet-secici" role="group" aria-label="Kategori filtresi">
                {KATEGORI_SECENEKLERI.map(([deger, etiket]) => (
                  <button
                    key={deger}
                    type="button"
                    className={`siddet-dugmesi${category === deger ? ' secili' : ''}`}
                    aria-pressed={category === deger}
                    onClick={() => setCategory(deger)}
                  >
                    {etiket}
                  </button>
                ))}
              </div>
            }
            yukleniyor={loading}
            cekiliyor={fetching}
            onYenile={() => loadEntries()}
            onRapor={handleExport}
            onTemizle={handleClearCache}
            onCek={handleFetchK8s}
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

export default KubernetesComponent
