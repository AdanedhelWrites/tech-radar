import { haberOkumaKaydi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'

// Gundem sutunu (spec 2026-10-31 G3, §6): bes bolumun son kayitlari, created_at azalan tek liste.
// Bolum rengi tema.css'te (.bolum-<ad>); renk tek basina anlam tasimaz, bolum adi yazili.

const BOLUM_ADI = {
  news: 'Siber Güvenlik',
  kubernetes: 'Kubernetes',
  sre: 'SRE',
  devtools: 'DevTools',
  ai: 'Yapay Zeka',
}

export default function Gundem({ ogeler, hata, onSec }) {
  let icerik
  if (hata) icerik = <p className="genel-bos">Gündem bilgisi alınamadı.</p>
  else if (!ogeler) icerik = <p className="genel-bos">Yükleniyor…</p>
  else if (ogeler.length === 0) icerik = <p className="genel-bos">Gündemde kayıt bulunmuyor.</p>
  else {
    icerik = (
      <ul className="gundem-liste">
        {ogeler.map(({ bolum, kayit }) => {
          const alt = [BOLUM_ADI[bolum], kayit.source, goreliZaman(kayit.created_at)].filter(Boolean).join(' · ')
          return (
            <li key={`${bolum}-${kayit.id}`}>
              <button type="button" className="gundem-ogesi" onClick={() => onSec(haberOkumaKaydi(kayit, bolum))}>
                <span className={`gundem-nokta bolum-${bolum}`} aria-hidden="true" />
                <span className="gundem-baslik">{kayit.turkish_title || kayit.original_title}</span>
                <small>{alt}</small>
              </button>
            </li>
          )
        })}
      </ul>
    )
  }

  return (
    <section className="cam-kart gundem" aria-labelledby="gundem-baslik">
      <h2 id="gundem-baslik" className="etiket-kucuk">Gündem</h2>
      {icerik}
    </section>
  )
}
