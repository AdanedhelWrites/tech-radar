import toast from 'react-hot-toast';
import { useState, useEffect, useMemo } from 'react'
import { Form, Spinner, Alert, Dropdown } from 'react-bootstrap'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import useSeciliKayit from '../hooks/useSeciliKayit'
import { kacis, guvenliHref } from '../utils/html'
import { cveOkumaKaydi } from '../utils/okumaKaydi'
import useZiyaretTabani from '../hooks/useZiyaretTabani'
import { goreliZaman } from '../utils/zaman'
import { ceviriEtiketiHtml } from './CeviriEtiketi'
import OkumaPaneli from './okuma/OkumaPaneli'
import CveSatiri from './cve/CveSatiri'
import {
  FaDownload, FaSync, FaTrash, FaFileExport, FaExclamationTriangle,
  FaDatabase, FaGithub, FaShieldVirus, FaClock, FaFilter
} from 'react-icons/fa'
import { cveApi, istekHataMesaji } from '../services/api'

// Zafiyetler sayfasi (spec 2026-10-31 G4): ustte kompakt filtre ve eylem cubugu, altinda tam
// genislikte liste, detay ortak okuma panelinde (?kayit=<id>, hooks/useSeciliKayit).

const sources = [
  { id: 'source1', name: 'NVD', value: 'NVD', icon: FaDatabase },
  { id: 'source2', name: 'GitHub Advisory', value: 'GitHub Advisory', icon: FaGithub },
  { id: 'source3', name: 'Tenable', value: 'Tenable', icon: FaShieldVirus },
  // 2026-10-14: CIRCL (source4) cikarildi; /api/last artik CVE donmuyor, NVD + GitHub Advisory kapsiyor
  { id: 'source5', name: 'NVD Güncel', value: 'NVD Güncel', icon: FaClock },
  { id: 'source6', name: 'CISA KEV', value: 'CISA KEV', icon: FaExclamationTriangle },
]

const severityOptions = [
  { value: 'all', label: 'Tümü' },
  { value: 'critical', label: 'Kritik', min: 9.0, max: 10.0 },
  { value: 'high', label: 'Yüksek', min: 7.0, max: 8.9 },
  { value: 'medium', label: 'Orta', min: 4.0, max: 6.9 },
  { value: 'low', label: 'Düşük', min: 0, max: 3.9 },
]

const GUN_SECENEKLERI = Array.from({ length: 15 }, (_, i) => i + 1)

// Veritabani siddet dagilimi: once bilinen siralama, sonra digerleri
const SIDDET_SIRASI = ['Kritik', 'Yüksek', 'Orta', 'Düşük', 'Bilinmiyor']

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

const sayi = (n) => Number(n || 0).toLocaleString('tr-TR')

function CVEComponent() {
  const [cves, setCVEs] = useState([])
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
  // "Yeni" rozeti tabani: sekme basina (hooks/useZiyaretTabani, karar R9); bu sayfa yazmaz
  const sonZiyaret = useZiyaretTabani()
  // Secim id ile cozulur: periyodik yenileme acik paneli kapatmaz, filtre degisince de acik kalir
  const { secili, sec, kapat } = useSeciliKayit(cves)
  const okumaKaydi = useMemo(() => (secili ? cveOkumaKaydi(secili) : null), [secili])

  // Diger bes bilesenle ayni kalip: cekim surerken yeni kayitlar kendiliginden ekrana duser
  // Sekme arka plandayken durur (hooks/useAraliklaYenile)
  useAraliklaYenile(() => loadCVEs(true), 5000)

  useEffect(() => {
    loadCVEs()
    loadStats()
  }, [])

  const loadCVEs = async (silent = false) => {
    try {
      if (!silent) setLoading(true)
      const response = await cveApi.getCVEs()
      if (response.data.success) {
        setCVEs(response.data.data)
      }
    } catch (err) {
      if (!silent) setError('CVE verileri yüklenirken hata oluştu')
      console.error(err)
    } finally {
      if (!silent) setLoading(false)
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
        loadStats()
        toast.success("CVE çekimi başladı! Kayıtlar otomatik olarak ekrana yansıyacak.", { icon: "🚀", duration: 4000 })
      } else {
        setError(response.data.message)
      }
    } catch (err) {
      setError(istekHataMesaji(err, 'CVE verileri getirilirken hata oluştu'))
    } finally {
      setFetching(false)
    }
  }

  const handleClearCache = async () => {
    if (!window.confirm('Tüm CVE verileri silinecek ve sıfırlanacak. Emin misiniz?')) return

    try {
      await cveApi.clearCache()
      // Liste bosalinca acik kayit cozulemez, panel kendiliginden kapanir
      setCVEs([])
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
  <span class="cveid">${kacis(item.cve_id || '')}</span>
  <span class="badge" style="background:${severityColor(item.severity)}">${kacis(item.severity || 'Bilinmiyor')}</span>
  ${ceviriEtiketiHtml(item)}
  ${item.cvss_score ? `<span class="score">CVSS: ${kacis(item.cvss_score)}</span>` : ''}
  <span class="date">${kacis(item.published_date || '')}</span>
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

  const filteredCVEs = severityFilter === 'all'
    ? cves
    : cves.filter(cve => {
      const opt = severityOptions.find(o => o.value === severityFilter)
      if (!opt || !cve.cvss_score) return false
      return cve.cvss_score >= opt.min && cve.cvss_score <= opt.max
    })

  const seciliKaynakSayisi = sources.filter(s => selectedSources[s.value]).length
  const bySource = stats.by_source || {}
  // Secenekler disinda veritabaninda kaydi kalan kaynaklar (or. 2026-10-14'te cikarilan CIRCL)
  const digerKaynaklar = Object.entries(bySource).filter(([ad]) => !sources.some(s => s.value === ad))
  const siddetDagilimi = Object.entries(stats.by_severity || {}).sort(([a], [b]) => {
    const sira = (s) => (SIDDET_SIRASI.includes(s) ? SIDDET_SIRASI.indexOf(s) : SIDDET_SIRASI.length)
    return sira(a) - sira(b)
  })

  let liste
  if (loading) {
    liste = <p className="liste-bos">CVE kayıtları yükleniyor…</p>
  } else if (filteredCVEs.length === 0) {
    liste = (
      <p className="liste-bos">
        {cves.length === 0
          ? 'CVE listesi boş. Kayıt almak için "Çek" düğmesini kullanın.'
          : 'Bu filtreyle eşleşen CVE bulunamadı.'}
      </p>
    )
  } else {
    liste = (
      <ul className="oncelikli-liste cve-listesi">
        {filteredCVEs.map(item => (
          <li key={item.id ?? item.cve_id}>
            <CveSatiri cve={item} sonZiyaret={sonZiyaret} onSec={c => sec(c.id)} />
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="bolum-sayfasi">
      <div className="sayfa-kafa">
        <h1 className="sayfa-baslik">Zafiyetler</h1>
        <div className="veritabani-ozeti">
          <span>{`Toplam ${sayi(stats.total)} kayıt`}</span>
          {stats.last_update && (
            <span title={new Date(stats.last_update).toLocaleString('tr-TR')}>
              {`Son güncelleme ${goreliZaman(stats.last_update)}`}
            </span>
          )}
          {siddetDagilimi.length > 0 && (
            <span className="siddet-dagilimi" aria-label="Veritabanı şiddet dağılımı">
              {siddetDagilimi.map(([severity, count]) => (
                <span key={severity} className={`rozet ${getSeverityClass(severity)}`}>
                  {`${severity} ${sayi(count)}`}
                </span>
              ))}
            </span>
          )}
        </div>
      </div>

      <section className="filtre-cubugu cam-kart" aria-label="Filtreler ve eylemler">
        <div className="filtre-gruplari">
          <label className="filtre-grubu">
            <span className="filtre-etiketi">Dönem</span>
            <Form.Select
              size="sm"
              className="cubuk-secim"
              value={days}
              onChange={(e) => setDays(e.target.value)}
              aria-label="Kaç günlük CVE çekilecek"
            >
              {GUN_SECENEKLERI.map(g => <option key={g} value={g}>{`Son ${g} gün`}</option>)}
            </Form.Select>
          </label>

          <Dropdown autoClose="outside" className="filtre-grubu">
            <Dropdown.Toggle variant="" size="sm" className="cubuk-dugme" id="cve-kaynaklari">
              <FaFilter aria-hidden="true" />
              {`Kaynaklar ${seciliKaynakSayisi}/${sources.length}`}
            </Dropdown.Toggle>
            <Dropdown.Menu className="kaynak-menusu">
              {sources.map(source => {
                const IconComp = source.icon
                return (
                  <Form.Check
                    key={source.id}
                    type="checkbox"
                    id={source.id}
                    className="kaynak-secenegi"
                    checked={selectedSources[source.value]}
                    onChange={() => toggleSource(source.value)}
                    label={
                      <>
                        <IconComp aria-hidden="true" />
                        <span className="kaynak-adi">{source.name}</span>
                        <span className="kaynak-sayisi">{sayi(bySource[source.value])}</span>
                      </>
                    }
                  />
                )
              })}
              {digerKaynaklar.length > 0 && (
                <p className="kaynak-diger">
                  {`Diğer kayıtlar: ${digerKaynaklar.map(([ad, n]) => `${ad} ${sayi(n)}`).join(', ')}`}
                </p>
              )}
            </Dropdown.Menu>
          </Dropdown>

          <div className="filtre-grubu siddet-secici" role="group" aria-label="CVSS şiddet filtresi">
            {severityOptions.map(opt => (
              <button
                key={opt.value}
                type="button"
                className={`siddet-dugmesi ${opt.value}${severityFilter === opt.value ? ' secili' : ''}`}
                aria-pressed={severityFilter === opt.value}
                onClick={() => setSeverityFilter(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="eylem-gruplari">
          <button
            type="button"
            className="cubuk-dugme"
            onClick={() => loadCVEs()}
            disabled={loading}
            title="Listeyi yenile"
          >
            <FaSync aria-hidden="true" />Yenile
          </button>
          <button
            type="button"
            className="cubuk-dugme"
            onClick={handleExport}
            title="CVE zafiyetlerini HTML rapor olarak indir"
          >
            <FaFileExport aria-hidden="true" />HTML rapor
          </button>
          <button
            type="button"
            className="cubuk-dugme tehlike"
            onClick={handleClearCache}
            title="Tüm CVE verilerini sil ve sıfırla"
          >
            <FaTrash aria-hidden="true" />Önbelleği temizle
          </button>
          <button
            type="button"
            className="cubuk-dugme birincil"
            onClick={handleFetchCVEs}
            disabled={fetching}
            title={`Seçili kaynaklardan son ${days} günün CVE kayıtlarını çek`}
          >
            {fetching
              ? <><Spinner size="sm" aria-hidden="true" />Çekiliyor…</>
              : <><FaDownload aria-hidden="true" />Çek</>}
          </button>
        </div>
      </section>

      <p className="liste-sayaci" aria-live="polite">
        {severityFilter === 'all'
          ? `${cves.length} CVE gösteriliyor`
          : `${filteredCVEs.length} / ${cves.length} CVE gösteriliyor`}
      </p>

      {liste}

      <OkumaPaneli kayit={okumaKaydi} onKapat={kapat} />

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
    </div>
  )
}

export default CVEComponent
