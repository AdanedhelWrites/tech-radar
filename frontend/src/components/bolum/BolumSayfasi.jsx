import { useMemo } from 'react'
import { Form, Spinner, Dropdown } from 'react-bootstrap'
import { FaDownload, FaSync, FaTrash, FaFileExport, FaFilter } from 'react-icons/fa'
import useSeciliKayit from '../../hooks/useSeciliKayit'
import { haberOkumaKaydi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'
import CeviriEtiketi from '../CeviriEtiketi'
import OkumaPaneli from '../okuma/OkumaPaneli'

// Bes haber bolumunun ortak iskeleti (spec 2026-10-31 G4-G5): sayfa basligi ve veritabani ozeti,
// kompakt filtre/eylem cubugu yuvasi, tam genislikte liste, detay ortak okuma panelinde
// (?kayit=<id>, hooks/useSeciliKayit). Zafiyetler sayfasiyla (CVEComponent) ayni siniflar.
// Veri yukleme, cekme/temizleme/rapor ve bolume ozgu filtreler bolum bileseninde kalir.

const sayi = (n) => Number(n || 0).toLocaleString('tr-TR')
const metin = (d) => (typeof d === 'string' ? d : '')

// Liste satiri: Turkce baslik (yoksa orijinal + ceviri rozeti), bilgi rozetleri, kaynak, goreli zaman
function HaberSatiri({ kayit, bolum, onSec }) {
  const trBaslik = metin(kayit.turkish_title)
  const { rozetler } = haberOkumaKaydi(kayit, bolum)
  return (
    <button type="button" className="oncelikli-satir haber-satiri" onClick={() => onSec(kayit)}>
      <span className="satir-govde">
        <span className="satir-baslik" lang={trBaslik ? 'tr' : 'en'}>
          {trBaslik || metin(kayit.original_title)}
        </span>
        {(rozetler.length > 0 || !trBaslik) && (
          <span className="satir-rozetler">
            {rozetler.map((r, i) => <span key={i} className={`rozet ${r.tur}`}>{r.metin}</span>)}
            {!trBaslik && <CeviriEtiketi kayit={kayit} className="" />}
          </span>
        )}
      </span>
      <span className="satir-sag">
        <span><span className={`gundem-nokta bolum-${bolum}`} aria-hidden="true" />{kayit.source}</span>
        <span>{goreliZaman(kayit.created_at)}</span>
      </span>
    </button>
  )
}

// Filtre/eylem cubugu: donem, kaynak acilir menusu, bolume ozgu ek filtre (ekFiltre), Yenile,
// HTML rapor, onbellegi temizle, Cek. Cek suresince dugme doner (eski tam ekran bekleme penceresi yok).
export function BolumCubugu({
  kimlik, gun, gunSecenekleri, onGunDegis,
  kaynaklar, seciliKaynaklar, onKaynakDegis, kaynakSayilari = {},
  ekFiltre = null,
  yukleniyor, cekiliyor, onYenile, onRapor, onTemizle, onCek,
}) {
  const seciliSayisi = kaynaklar.filter(k => seciliKaynaklar[k.value]).length
  // Secenekler disinda veritabaninda kaydi kalan kaynaklar (or. 2026-10-14'te cikarilan kaynaklar)
  const digerKaynaklar = Object.entries(kaynakSayilari).filter(([ad]) => !kaynaklar.some(k => k.value === ad))

  return (
    <section className="filtre-cubugu cam-kart" aria-label="Filtreler ve eylemler">
      <div className="filtre-gruplari">
        <label className="filtre-grubu">
          <span className="filtre-etiketi">Dönem</span>
          <Form.Select
            size="sm"
            className="cubuk-secim"
            value={gun}
            onChange={(e) => onGunDegis(Number(e.target.value))}
            aria-label="Kaç günlük kayıt çekilecek"
          >
            {gunSecenekleri.map(g => <option key={g} value={g}>{`Son ${g} gün`}</option>)}
          </Form.Select>
        </label>

        <Dropdown autoClose="outside" className="filtre-grubu">
          <Dropdown.Toggle variant="" size="sm" className="cubuk-dugme" id={`${kimlik}-kaynaklari`}>
            <FaFilter aria-hidden="true" />
            {`Kaynaklar ${seciliSayisi}/${kaynaklar.length}`}
          </Dropdown.Toggle>
          <Dropdown.Menu className="kaynak-menusu">
            {kaynaklar.map(kaynak => {
              const Ikon = kaynak.icon
              return (
                <Form.Check
                  key={kaynak.id}
                  type="checkbox"
                  id={kaynak.id}
                  className="kaynak-secenegi"
                  checked={seciliKaynaklar[kaynak.value]}
                  onChange={() => onKaynakDegis(kaynak.value)}
                  label={
                    <>
                      <Ikon aria-hidden="true" />
                      <span className="kaynak-adi">{kaynak.name}</span>
                      <span className="kaynak-sayisi">{sayi(kaynakSayilari[kaynak.value])}</span>
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

        {ekFiltre}
      </div>

      <div className="eylem-gruplari">
        <button type="button" className="cubuk-dugme" onClick={onYenile} disabled={yukleniyor} title="Listeyi yenile">
          <FaSync aria-hidden="true" />Yenile
        </button>
        <button type="button" className="cubuk-dugme" onClick={onRapor} title="Kayıtları HTML rapor olarak indir">
          <FaFileExport aria-hidden="true" />HTML rapor
        </button>
        <button type="button" className="cubuk-dugme tehlike" onClick={onTemizle} title="Bu bölümün bütün kayıtlarını sil ve sıfırla">
          <FaTrash aria-hidden="true" />Önbelleği temizle
        </button>
        <button
          type="button"
          className="cubuk-dugme birincil"
          onClick={onCek}
          disabled={cekiliyor}
          title={`Seçili kaynaklardan son ${gun} günün kayıtlarını çek`}
        >
          {cekiliyor
            ? <><Spinner size="sm" aria-hidden="true" />Çekiliyor…</>
            : <><FaDownload aria-hidden="true" />Çek</>}
        </button>
      </div>
    </section>
  )
}

export default function BolumSayfasi({
  bolum, baslik, kayitlar, yukleniyor, cubuk,
  istatistik = null, dagilim = [], filtre = null,
}) {
  // Secim tum liste uzerinden cozulur: periyodik yenileme de filtre degisikligi de acik paneli kapatmaz
  const { secili, sec, kapat } = useSeciliKayit(kayitlar)
  const okumaKaydi = useMemo(() => (secili ? haberOkumaKaydi(secili, bolum) : null), [secili, bolum])
  const gosterilenler = filtre ? kayitlar.filter(filtre) : kayitlar

  let liste
  if (yukleniyor) {
    liste = <p className="liste-bos">Kayıtlar yükleniyor…</p>
  } else if (gosterilenler.length === 0) {
    liste = (
      <p className="liste-bos">
        {kayitlar.length === 0
          ? 'Liste boş. Kayıt almak için "Çek" düğmesini kullanın.'
          : 'Bu filtreyle eşleşen kayıt bulunamadı.'}
      </p>
    )
  } else {
    liste = (
      <ul className="oncelikli-liste">
        {gosterilenler.map(kayit => (
          <li key={kayit.id}>
            <HaberSatiri kayit={kayit} bolum={bolum} onSec={k => sec(k.id)} />
          </li>
        ))}
      </ul>
    )
  }

  return (
    <div className="bolum-sayfasi">
      <div className="sayfa-kafa">
        <h1 className="sayfa-baslik">{baslik}</h1>
        {istatistik && (
          <div className="veritabani-ozeti">
            <span>{`Toplam ${sayi(istatistik.total)} kayıt`}</span>
            {istatistik.last_update && (
              <span title={new Date(istatistik.last_update).toLocaleString('tr-TR')}>
                {`Son güncelleme ${goreliZaman(istatistik.last_update)}`}
              </span>
            )}
            {dagilim.length > 0 && (
              <span className="siddet-dagilimi" aria-label="Veritabanı dağılımı">
                {dagilim.map(([etiket, adet]) => (
                  <span key={etiket} className="rozet bilgi">{`${etiket} ${sayi(adet)}`}</span>
                ))}
              </span>
            )}
          </div>
        )}
      </div>

      {cubuk}

      <p className="liste-sayaci" aria-live="polite">
        {filtre
          ? `${gosterilenler.length} / ${kayitlar.length} kayıt gösteriliyor`
          : `${kayitlar.length} kayıt gösteriliyor`}
      </p>

      {liste}

      <OkumaPaneli kayit={okumaKaydi} onKapat={kapat} />
    </div>
  )
}
