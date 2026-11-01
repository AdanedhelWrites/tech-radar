import { useId, useState } from 'react'
import { Offcanvas } from 'react-bootstrap'
import CeviriEtiketi from '../CeviriEtiketi'
import { okumaIcerigi, prParcalari } from '../../utils/okuma'
import { ceviriBekliyor } from '../../utils/okumaKaydi'
import { skorSinifi } from '../../utils/cve'

// Alti bolumun ve Genel Bakis'in ortak okuma paneli (spec 2026-10-31 G5). Girdi OkumaKaydi
// (utils/okumaKaydi.js). Varsayilan Turkce; orijinal metin istenirse Turkce govdenin altinda acilir.
// Ceviri yoksa orijinal uyariyla gosterilir: panel hicbir zaman bos gorunmez.

const SKOR_ETIKETI = { kritik: 'KRİTİK', yuksek: 'YÜKSEK', orta: 'ORTA', '': 'DÜŞÜK' }

// React href'i icin ham adres yalniz http(s) ise kullanilir; kacis React'in isi (karar R2,
// guvenliHref & isaretini &amp; yapar ve yalniz HTML sablonlari icindir).
const HTTP_ADRES = /^https?:\/\//i
const guvenliAdres = (adres) => {
  const a = typeof adres === 'string' ? adres.trim() : ''
  return HTTP_ADRES.test(a) ? a : null
}

const DisBaglanti = ({ href, children, className }) => (
  <a href={href} target="_blank" rel="noopener noreferrer" className={className}>{children}</a>
)

// Kubernetes degisiklik gunlugunde (kayit.prAdresi) "#123" PR etiketi baglanti olur; digerlerinde duz metin
const Paragraf = ({ metin, prAdresi }) => (prAdresi
  ? prParcalari(metin).map((p, i) => (p.pr
    ? <DisBaglanti key={i} href={`${prAdresi}${p.pr}`} className="okuma-pr">{`#${p.pr}`}</DisBaglanti>
    : p.metin))
  : metin)

function PanelIcerigi({ kayit, baslikId }) {
  const [orijinalAcik, setOrijinalAcik] = useState(false)
  const orijinalId = useId()
  const icerik = okumaIcerigi(kayit)
  const { tamamenCevrilmedi } = icerik
  const baslikEn = tamamenCevrilmedi || ceviriBekliyor(kayit.ham)
  const orijinalDugmesi = !tamamenCevrilmedi && icerik.orijinal.length > 0
  // Saglayicisiz ve hic cevrilmemis kayitta CeviriEtiketi'nin "Cevrilmedi" rozeti uyariyi tekrar ederdi
  const ceviriRozeti = !(tamamenCevrilmedi && !kayit.ham?.translation_provider)
  const sinif = kayit.skor == null ? '' : skorSinifi(kayit.skor)
  const kimlik = kayit.ustBaslik && kayit.ustBaslik !== kayit.baslik ? kayit.ustBaslik : null
  const altBilgi = [kayit.kaynak, kayit.tarih].filter(Boolean).join(' · ')
  const kaynakAdresi = guvenliAdres(kayit.link)
  const altBolum = kayit.ekAlanlar.length > 0 || kayit.referanslar.length > 0 || kaynakAdresi

  return (
    <>
      <Offcanvas.Header closeButton closeLabel="Kapat" className="okuma-kafa">
        <div className="okuma-kafa-ic">
          <div className="okuma-baslik-alani">
            {kimlik && <div className="okuma-kimlik">{kimlik}</div>}
            <Offcanvas.Title as="h2" id={baslikId} className="okuma-baslik" lang={baslikEn ? 'en' : 'tr'}>{kayit.baslik}</Offcanvas.Title>
            {altBilgi && <div className="okuma-alt-bilgi">{altBilgi}</div>}
          </div>
          {kayit.skor != null && (
            <div className={`skor-kutusu ${sinif}`}>
              {kayit.skor.toFixed(1)}
              <small>{SKOR_ETIKETI[sinif]}</small>
            </div>
          )}
        </div>
      </Offcanvas.Header>

      <Offcanvas.Body className="okuma-govde">
        <div className="okuma-rozetler">
          {kayit.rozetler.map((r, i) => <span key={i} className={`rozet ${r.tur}`}>{r.metin}</span>)}
          {ceviriRozeti && <CeviriEtiketi kayit={kayit.ham} className="" />}
        </div>

        {kayit.kevMeta && (
          <p className="okuma-kev">
            <span>{`KEV'e eklenme: ${kayit.kevMeta.kevEklenme}`}</span>
            {kayit.kevMeta.sonTarih && (
              <>
                <span aria-hidden="true"> · </span>
                <span>{`Son işlem tarihi: ${kayit.kevMeta.sonTarih}`}</span>
              </>
            )}
          </p>
        )}

        {tamamenCevrilmedi && (
          <div className="okuma-uyari" role="note">
            <span className="rozet uyari">Çevrilmedi: orijinal metin</span>
            <span>Bu kaydın Türkçe çevirisi bulunmuyor; metin özgün dilinde gösteriliyor.</span>
          </div>
        )}

        {orijinalDugmesi && (
          <button
            type="button"
            className="okuma-dugme"
            aria-expanded={orijinalAcik}
            aria-controls={orijinalAcik ? orijinalId : undefined}
            onClick={() => setOrijinalAcik(a => !a)}
          >
            {orijinalAcik ? 'Orijinali gizle' : 'Orijinali göster'}
          </button>
        )}

        {icerik.paragraflar.length === 0 ? (
          <p className="okuma-bos">İçerik bulunmuyor.</p>
        ) : (
          <div className="okuma-metni" lang={tamamenCevrilmedi ? 'en' : 'tr'}>
            {icerik.paragraflar.map((p, i) => (p.cevrilmedi ? (
              <p key={i} className="cevrilmedi" lang="en">
                <span className="cevrilmedi-not" lang="tr">Bu paragraf çevrilemedi</span>
                <Paragraf metin={p.metin} prAdresi={kayit.prAdresi} />
              </p>
            ) : (
              <p key={i}><Paragraf metin={p.metin} prAdresi={kayit.prAdresi} /></p>
            )))}
          </div>
        )}

        {orijinalAcik && (
          <section id={orijinalId} className="okuma-orijinal" aria-label="Orijinal metin">
            <div className="etiket-kucuk">Orijinal metin</div>
            <div className="okuma-metni orijinal" lang="en">
              {icerik.orijinal.map((p, i) => <p key={i}><Paragraf metin={p} prAdresi={kayit.prAdresi} /></p>)}
            </div>
          </section>
        )}

        {altBolum && (
          <div className="okuma-alt">
            {kayit.ekAlanlar.length > 0 && (
              <dl className="okuma-ek-alanlar">
                {kayit.ekAlanlar.map((a, i) => (
                  <div key={i}>
                    <dt>{a.etiket}</dt>
                    <dd>{a.deger}</dd>
                  </div>
                ))}
              </dl>
            )}
            {kayit.referanslar.length > 0 && (
              <>
                <div className="etiket-kucuk">{`Referanslar (${kayit.referanslar.length})`}</div>
                <ul className="okuma-referanslar">
                  {kayit.referanslar.map((r, i) => {
                    const adres = guvenliAdres(r)
                    return <li key={i}>{adres ? <DisBaglanti href={adres}>{r}</DisBaglanti> : <span>{r}</span>}</li>
                  })}
                </ul>
              </>
            )}
            {kaynakAdresi && (
              <DisBaglanti href={kaynakAdresi} className="okuma-kaynak-linki">Orijinal kaynağa git →</DisBaglanti>
            )}
          </div>
        )}
      </Offcanvas.Body>
    </>
  )
}

export default function OkumaPaneli({ kayit, onKapat }) {
  const baslikId = useId()
  // Kapanirken (kayit null) kayma animasyonu bitene dek son kayit gosterilmeye devam eder
  const [gosterilen, setGosterilen] = useState(kayit)
  if (kayit && kayit !== gosterilen) setGosterilen(kayit)

  return (
    <Offcanvas
      show={!!kayit}
      onHide={onKapat}
      placement="end"
      className="okuma-paneli"
      aria-labelledby={baslikId}
    >
      {gosterilen && (
        // Baska kayda gecince "orijinal acik" durumu sifirlanir; ayni kaydin yenilenmis nesnesinde korunur
        <PanelIcerigi key={`${gosterilen.id}|${gosterilen.link}`} kayit={gosterilen} baslikId={baslikId} />
      )}
    </Offcanvas>
  )
}
