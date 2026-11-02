import { Link } from 'react-router-dom'
import { cveOkumaKaydi } from '../../utils/okumaKaydi'
import CveSatiri from '../cve/CveSatiri'

// Oncelikli zafiyetler (spec 2026-10-31 G3): /api/ozet/ priority kayitlari. Satir Zafiyetler
// sayfasiyla ortak (cve/CveSatiri); tiklaninca okuma paneli yerinde acilir.

export default function OncelikliListe({ kayitlar, hata, sonZiyaret, onSec }) {
  let icerik
  if (hata) icerik = <p className="genel-bos">Öncelikli zafiyet listesi şu anda gösterilemiyor.</p>
  else if (!kayitlar) icerik = <p className="genel-bos">Yükleniyor…</p>
  else if (kayitlar.length === 0) icerik = <p className="genel-bos">Son 7 günde öncelikli zafiyet kaydı bulunmuyor.</p>
  else {
    icerik = (
      <ul className="oncelikli-liste">
        {kayitlar.map(cve => (
          <li key={cve.id ?? cve.cve_id}>
            <CveSatiri cve={cve} sonZiyaret={sonZiyaret} onSec={c => onSec(cveOkumaKaydi(c))} />
          </li>
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
