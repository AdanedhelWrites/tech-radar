import { useMemo } from 'react'
import useBolumVerisi from '../hooks/useBolumVerisi'
import useSeciliKayit from '../hooks/useSeciliKayit'
import { cveOkumaKaydi } from '../utils/okumaKaydi'
import { skorSinifi } from '../utils/cve'
import useZiyaretTabani from '../hooks/useZiyaretTabani'
import { goreliZaman } from '../utils/zaman'
import OkumaPaneli from './okuma/OkumaPaneli'
import CveSatiri from './cve/CveSatiri'
import { ceviriRozeti } from './CeviriEtiketi'
import { BolumCubugu, HataUyarisi } from './bolum/BolumSayfasi'
import SayfaCubugu from './bolum/SayfaCubugu'
import { CVSS_SIRALAMASI, SIRALA_SECENEKLERI, sayimMetni } from './bolum/secenekler'
import {
  FaExclamationTriangle, FaDatabase, FaGithub, FaShieldVirus, FaClock
} from 'react-icons/fa'
import { cveApi } from '../services/api'

// Zafiyetler sayfasi (spec 2026-10-31 G4): ustte kompakt filtre ve eylem cubugu, altinda tam
// genislikte liste, detay ortak okuma panelinde (?kayit=<id>, hooks/useSeciliKayit).
// 2026-11-05 (filtre/sayfalama spec G4): donem, siralama (En yuksek CVSS dahil), kaynak ve onem
// sunucuda suzulur/siralanir, liste sayfalanir (adreste, ?onem=kritik&sirala=cvss&sayfa=2). Veri ve
// eylemler bes haber bolumuyle ortak hooks/useBolumVerisi'nde; satir (CveSatiri) ve onem dugmeleri
// bu sayfaya ozgu.

const sources = [
  { id: 'source1', name: 'NVD', value: 'NVD', icon: FaDatabase },
  { id: 'source2', name: 'GitHub Advisory', value: 'GitHub Advisory', icon: FaGithub },
  { id: 'source3', name: 'Tenable', value: 'Tenable', icon: FaShieldVirus },
  // 2026-10-14: CIRCL (source4) cikarildi; /api/last artik CVE donmuyor, NVD + GitHub Advisory kapsiyor
  { id: 'source5', name: 'NVD Güncel', value: 'NVD Güncel', icon: FaClock },
  { id: 'source6', name: 'CISA KEV', value: 'CISA KEV', icon: FaExclamationTriangle },
]

// Onem (CVSS araligi, sunucuda): >=9, 7-8.9, 4-6.9, 0-3.9; skorsuz kayit yalniz Tumu'de.
// deger adrese yazilir ('' = Tumu); renk tema.css .siddet-dugmesi.<renk>
const ONEM_SECENEKLERI = [
  { deger: '', etiket: 'Tümü', renk: 'all' },
  { deger: 'kritik', etiket: 'Kritik', renk: 'critical' },
  { deger: 'yuksek', etiket: 'Yüksek', renk: 'high' },
  { deger: 'orta', etiket: 'Orta', renk: 'medium' },
  { deger: 'dusuk', etiket: 'Düşük', renk: 'low' },
]

const SIRALAMALAR = [...SIRALA_SECENEKLERI, CVSS_SIRALAMASI]

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

// Rapor rozetleri ham metin (utils/rapor sablonda kacislar): CVE kimligi, CVSS (renk skorla; 4 alti
// dusuk; skorsuzda saklanan severity metni), CISA KEV (liste satiri ve okuma paneliyle ayni kural:
// utils/okumaKaydi) ve ceviri etiketi (CeviriEtiketi ile ayni kural)
const raporRozetleri = (item) => {
  const rozetler = []
  if (item.cve_id) rozetler.push({ metin: item.cve_id, sinif: 'cveid' })
  if (Number.isFinite(item.cvss_score)) {
    rozetler.push({ metin: `CVSS ${item.cvss_score.toFixed(1)}`, sinif: skorSinifi(item.cvss_score) || 'dusuk' })
  } else {
    rozetler.push({ metin: item.severity || 'Bilinmiyor', sinif: 'skorsuz' })
  }
  if (cveOkumaKaydi(item).rozetler.some(r => r.tur === 'kev')) rozetler.push({ metin: 'CISA KEV', sinif: 'kev' })
  const ceviri = ceviriRozeti(item)
  if (ceviri) rozetler.push(ceviri)
  return rozetler
}

const TANIM = {
  kaynaklar: sources,
  api: {
    liste: (params) => cveApi.getCVEs(params),
    cek: (veri) => cveApi.fetchCVEs(veri),
    temizle: () => cveApi.clearCache(),
    istatistik: () => cveApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'CVE verileri yüklenirken hata oluştu',
    cekimHatasi: 'CVE verileri getirilirken hata oluştu',
    temizleOnayi: 'Tüm CVE verileri silinecek ve sıfırlanacak. Emin misiniz?',
    cekimBasladi: 'CVE çekimi başladı! Kayıtlar otomatik olarak ekrana yansıyacak.',
    raporBasligi: 'CVE zafiyetlerini HTML rapor olarak indir',
    temizleBasligi: 'Tüm CVE verilerini sil ve sıfırla',
    cekBasligi: (gun) => `Seçili kaynaklardan son ${gun} günün CVE kayıtlarını çek`,
  },
  rapor: {
    belgeBasligi: 'CVE Zafiyet Raporu',
    baslik: 'CVE Zafiyet Raporu',
    birim: 'zafiyet',
    dosyaOnEki: 'cve_zafiyet_raporu',
    ekRozetler: raporRozetleri,
  },
  ekAnahtarlar: ['onem'],
  // Gecersiz ?onem= istege gitmez (Tumu sayilir)
  ekDegerler: { onem: ONEM_SECENEKLERI.map(o => o.deger).filter(Boolean) },
  siralaSecenekleri: SIRALAMALAR,
  raporAciklamaEki: (sorgu) => ONEM_SECENEKLERI.find(o => o.deger && o.deger === sorgu.onem)?.etiket ?? '',
}

// onem: hook'ta dogrulanmis deger ('' = Tumu)
function OnemFiltresi({ onem: gecerli, onDegis }) {
  return (
    <div className="filtre-grubu siddet-secici" role="group" aria-label="CVSS şiddet filtresi">
      {ONEM_SECENEKLERI.map(opt => (
        <button
          key={opt.renk}
          type="button"
          className={`siddet-dugmesi ${opt.renk}${gecerli === opt.deger ? ' secili' : ''}`}
          aria-pressed={gecerli === opt.deger}
          onClick={() => onDegis(opt.deger)}
        >
          {opt.etiket}
        </button>
      ))}
    </div>
  )
}

function CVEComponent() {
  const veri = useBolumVerisi(TANIM)
  const { liste, istatistik: stats } = veri
  const { kayitlar, yukleniyor, sorgu } = liste
  // "Yeni" rozeti tabani: sekme basina (hooks/useZiyaretTabani, karar R9); bu sayfa yazmaz
  const sonZiyaret = useZiyaretTabani()
  // Secim id ile cozulur: periyodik yenileme, sayfa ya da filtre degisikligi acik paneli kapatmaz
  const { secili, sec, kapat } = useSeciliKayit(kayitlar)
  const okumaKaydi = useMemo(() => (secili ? cveOkumaKaydi(secili) : null), [secili])

  const siddetDagilimi = Object.entries(stats.by_severity || {}).sort(([a], [b]) => {
    const sira = (s) => (SIDDET_SIRASI.includes(s) ? SIDDET_SIRASI.indexOf(s) : SIDDET_SIRASI.length)
    return sira(a) - sira(b)
  })
  // Yuklenirken ya da yeni sorgu hatayla bittiyse eski sorgunun sayilari gosterilmez (bolum/BolumSayfasi)
  const sonucVar = liste.guncel && !yukleniyor && kayitlar.length > 0

  let listeOgesi
  if (yukleniyor) {
    listeOgesi = <p className="liste-bos">CVE kayıtları yükleniyor…</p>
  } else if (kayitlar.length === 0) {
    listeOgesi = (
      <p className="liste-bos">
        {Number(stats.total) > 0
          ? 'Bu filtreyle eşleşen kayıt bulunamadı.'
          : 'CVE listesi boş. Kayıt almak için "Çek" düğmesini kullanın.'}
      </p>
    )
  } else {
    listeOgesi = (
      <ul className="oncelikli-liste cve-listesi">
        {kayitlar.map(item => (
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

      <BolumCubugu
        kimlik="cve"
        {...veri.cubukOzellikleri(kapat)}
        ekFiltre={<OnemFiltresi onem={sorgu.onem} onDegis={(onem) => liste.degistir({ onem })} />}
      />

      <p className="liste-sayaci" aria-live="polite">
        {sonucVar
          ? sayimMetni({ gun: sorgu.gun, toplam: liste.toplam, sayfa: liste.sayfa, boyut: liste.boyut, adet: kayitlar.length })
          : ''}
      </p>

      {listeOgesi}

      {sonucVar && <SayfaCubugu sayfa={liste.sayfa} sayfaSayisi={liste.sayfaSayisi} onSayfa={liste.sayfayaGit} />}

      <OkumaPaneli kayit={okumaKaydi} onKapat={kapat} />

      <HataUyarisi metin={veri.hata} onKapat={veri.hatayiKapat} />
    </div>
  )
}

export default CVEComponent
