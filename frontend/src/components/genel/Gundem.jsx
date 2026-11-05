import { haberOkumaKaydi, cevrilmediMi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'

// Gundem sutunu (spec 2026-11-05 G4): sunucunun olay puanina gore sirali olaylari; olay temsilci
// kayitla gosterilir, 2+ kaynakli olayda "N kaynak" rozeti (ipucunda kaynak adlari) bulunur.
// Bolum rengi tema.css'te (.bolum-<ad>); renk tek basina anlam tasimaz, bolum adi yazili.

const BOLUM_ADI = {
  news: 'Siber Güvenlik',
  kubernetes: 'Kubernetes',
  sre: 'SRE',
  devtools: 'DevTools',
  ai: 'Yapay Zeka',
}

export default function Gundem({ olaylar, hata, onSec }) {
  let icerik
  if (hata) icerik = <p className="genel-bos">Gündem bilgisi alınamadı.</p>
  else if (!olaylar) icerik = <p className="genel-bos">Yükleniyor…</p>
  else if (olaylar.length === 0) icerik = <p className="genel-bos">Gündemde kayıt bulunmuyor.</p>
  else {
    icerik = (
      <ul className="gundem-liste">
        {olaylar.map((olay) => {
          const { bolum, kayit } = olay
          const alt = [BOLUM_ADI[bolum], kayit.source].filter(Boolean).join(' · ')
          const zaman = goreliZaman(olay.son || kayit.created_at)
          return (
            <li key={`${bolum}-${kayit.id}`}>
              <button type="button" className="gundem-ogesi" onClick={() => onSec(haberOkumaKaydi(kayit, bolum))}>
                <span className={`gundem-nokta bolum-${bolum}`} aria-hidden="true" />
                <span className="gundem-baslik" lang={cevrilmediMi(kayit) ? 'en' : 'tr'}>{kayit.turkish_title || kayit.original_title}</span>
                <small>
                  {alt}
                  {olay.kaynak_sayisi >= 2 && (
                    <>
                      {' '}
                      <span className="rozet bilgi" title={(olay.kaynaklar || []).join(', ')}>{`${olay.kaynak_sayisi} kaynak`}</span>
                    </>
                  )}
                  {zaman && ` · ${zaman}`}
                </small>
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
