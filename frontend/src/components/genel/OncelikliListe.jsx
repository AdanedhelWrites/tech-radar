import { Link } from 'react-router-dom'
import { skorSinifi, cveListeBasligi } from '../../utils/cve'
import { cveOkumaKaydi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'

// Oncelikli zafiyetler (spec 2026-10-31 G3): /api/ozet/ priority kayitlari. Satira tiklaninca
// okuma paneli acilir. "Yeni" = created_at son ziyaretten sonra; ilk ziyarette (deger yok) gosterilmez.

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

function Satir({ cve, sonZiyaretZamani, onSec }) {
  const okuma = cveOkumaKaydi(cve)
  // Kisa aciklama: KEV oneki atilmis govdenin ilk paragrafi (Turkce yoksa orijinal)
  const ozetMetni = (okuma.govdeTr || okuma.govdeOrijinal).split(/\n\s*\n/)[0].trim()
  const kev = !!cve.kev_added_date
  const olusma = zamanDamgasi(cve.created_at)
  const yeni = sonZiyaretZamani != null && olusma != null && olusma > sonZiyaretZamani
  const cweler = (Array.isArray(cve.cwe_ids) ? cve.cwe_ids.filter(Boolean) : []).slice(0, AZAMI_CWE)

  return (
    <li>
      <button type="button" className="oncelikli-satir" onClick={() => onSec(okuma)}>
        <SkorKutusu skor={cve.cvss_score} />
        <span className="satir-govde">
          <span className="satir-baslik">
            <span className="cve-kimlik">{cve.cve_id}</span>
            {cveListeBasligi(cve)}
          </span>
          {ozetMetni && (
            <span className="satir-ozet" lang={okuma.govdeTr ? 'tr' : 'en'}>{ozetMetni}</span>
          )}
          {(kev || yeni || cweler.length > 0) && (
            <span className="satir-rozetler">
              {kev && <span className="rozet kev">CISA KEV</span>}
              {yeni && <span className="rozet yeni">Yeni</span>}
              {cweler.map(c => <span key={c} className="rozet ur">{c}</span>)}
            </span>
          )}
        </span>
        <span className="satir-sag">
          <span>{cve.source}</span>
          <span>{goreliZaman(cve.created_at)}</span>
        </span>
      </button>
    </li>
  )
}

export default function OncelikliListe({ kayitlar, hata, sonZiyaret, onSec }) {
  const sonZiyaretZamani = zamanDamgasi(sonZiyaret)

  let icerik
  if (hata) icerik = <p className="genel-bos">Öncelikli zafiyet listesi şu anda gösterilemiyor.</p>
  else if (!kayitlar) icerik = <p className="genel-bos">Yükleniyor…</p>
  else if (kayitlar.length === 0) icerik = <p className="genel-bos">Son 7 günde öncelikli zafiyet kaydı bulunmuyor.</p>
  else {
    icerik = (
      <ul className="oncelikli-liste">
        {kayitlar.map(cve => (
          <Satir key={cve.id ?? cve.cve_id} cve={cve} sonZiyaretZamani={sonZiyaretZamani} onSec={onSec} />
        ))}
      </ul>
    )
  }

  return (
    <section className="oncelikli" aria-labelledby="oncelikli-baslik">
      <div className="bolum-basi">
        <h2 id="oncelikli-baslik" className="etiket-kucuk">Öncelikli Zafiyetler</h2>
        <Link to="/cve" className="tumu-baglantisi">Tümünü görüntüle →</Link>
      </div>
      {icerik}
    </section>
  )
}
