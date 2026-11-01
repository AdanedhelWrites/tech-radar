import { skorSinifi, cveListeBasligi } from '../../utils/cve'
import CeviriEtiketi from '../CeviriEtiketi'
import { cveOkumaKaydi, cevrilmediMi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'

// CVE liste satiri: Genel Bakis'taki oncelikli liste ve Zafiyetler sayfasi ayni satiri kullanir
// (spec 2026-10-31 G3-G4). Satir bir dugmedir: klavyeyle secilir, okuma panelini acar.
// "Yeni" = created_at son ziyaretten sonra; ilk ziyarette (sonZiyaret yok) gosterilmez.

const SKOR_ETIKETI = { kritik: 'KRİTİK', yuksek: 'YÜKSEK', orta: 'ORTA', '': 'DÜŞÜK' }
const AZAMI_CWE = 2

const zamanDamgasi = (iso) => {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : t
}

function SkorKutusu({ skor }) {
  if (!Number.isFinite(skor)) {
    return <span className="skor-kutusu">–<small>SKORSUZ</small></span>
  }
  const sinif = skorSinifi(skor)
  return <span className={`skor-kutusu ${sinif}`}>{skor.toFixed(1)}<small>{SKOR_ETIKETI[sinif]}</small></span>
}

export default function CveSatiri({ cve, sonZiyaret, onSec }) {
  const okuma = cveOkumaKaydi(cve)
  const cevrilmedi = cevrilmediMi(cve)
  // Kisa aciklama: KEV oneki atilmis govdenin ilk paragrafi (Turkce yoksa orijinal)
  const ozetMetni = (okuma.govdeTr || okuma.govdeOrijinal).split(/\n\s*\n/)[0].trim()
  // KEV, okuma panelindeki rozetle ayni kurala gore: CISA KEV kaynagi ya da KEV eklenme tarihi
  const kev = okuma.rozetler.some(r => r.tur === 'kev')
  const olusma = zamanDamgasi(cve.created_at)
  const sonZiyaretZamani = zamanDamgasi(sonZiyaret)
  const yeni = sonZiyaretZamani != null && olusma != null && olusma > sonZiyaretZamani
  const cweler = (Array.isArray(cve.cwe_ids) ? cve.cwe_ids.filter(Boolean) : []).slice(0, AZAMI_CWE)

  return (
    <button type="button" className="oncelikli-satir" onClick={() => onSec(cve)}>
      <SkorKutusu skor={cve.cvss_score} />
      <span className="satir-govde">
        <span className="satir-baslik" lang={cevrilmedi ? 'en' : 'tr'}>
          <span className="cve-kimlik">{cve.cve_id}</span>
          {cveListeBasligi(cve)}
        </span>
        {ozetMetni && (
          <span className="satir-ozet" lang={okuma.govdeTr ? 'tr' : 'en'}>{ozetMetni}</span>
        )}
        {(kev || yeni || cweler.length > 0 || cevrilmedi || cve.translation_provider) && (
          <span className="satir-rozetler">
            {kev && <span className="rozet kev">CISA KEV</span>}
            {yeni && <span className="rozet yeni">Yeni</span>}
            {cweler.map(c => <span key={c} className="rozet ur">{c}</span>)}
            <CeviriEtiketi kayit={cve} className="" />
          </span>
        )}
      </span>
      <span className="satir-sag">
        <span>{cve.source}</span>
        <span>{goreliZaman(cve.created_at)}</span>
      </span>
    </button>
  )
}
