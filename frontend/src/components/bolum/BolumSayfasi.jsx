import { useMemo } from 'react'
import { Alert, Form, Spinner, Dropdown } from 'react-bootstrap'
import { FaDownload, FaSync, FaTrash, FaFileExport, FaFilter } from 'react-icons/fa'
import useSeciliKayit from '../../hooks/useSeciliKayit'
import { haberOkumaKaydi, haberRozetleri, cevrilmediMi } from '../../utils/okumaKaydi'
import { goreliZaman } from '../../utils/zaman'
import CeviriEtiketi from '../CeviriEtiketi'
import OkumaPaneli from '../okuma/OkumaPaneli'
import SayfaCubugu from './SayfaCubugu'
import { cekimGunu, donemEtiketi, sayimMetni } from './secenekler'

// Bes haber bolumunun ortak iskeleti (spec 2026-10-31 G4-G5): sayfa basligi ve veritabani ozeti,
// kompakt filtre/eylem cubugu yuvasi, tam genislikte liste, detay ortak okuma panelinde
// (?kayit=<id>, hooks/useSeciliKayit). Zafiyetler sayfasiyla (CVEComponent) ayni siniflar.
// 2026-11-05 (filtre/sayfalama spec G4): liste sunucuda suzulmus tek sayfadir; sayim satiri gercek
// toplami ve gosterilen araligi, listenin altindaki SayfaCubugu sayfalari verir. Veri yukleme,
// cekme/temizleme/rapor bolum/HaberBolumu'nda.

const TUMU_DEGERI = 'tumu'

const sayi = (n) => Number(n || 0).toLocaleString('tr-TR')
const metin = (d) => (typeof d === 'string' ? d : '')

// Liste satiri: Turkce baslik (yoksa orijinal), bilgi rozetleri, ceviri rozeti, kaynak, goreli zaman.
// CeviriEtiketi her satirda (bulgu 6, 2026-10-21): basarisiz ceviride turkish_title Ingilizce basligin
// kopyasidir (needs_translation, saglayici yok); "Cevrilmedi" rozeti yalniz bos baslikta cikmamali.
function HaberSatiri({ kayit, bolum, onSec }) {
  const trBaslik = metin(kayit.turkish_title)
  const cevrilmedi = cevrilmediMi(kayit)
  const rozetler = haberRozetleri(kayit)
  return (
    <button type="button" className="oncelikli-satir haber-satiri" onClick={() => onSec(kayit)}>
      <span className="satir-govde">
        <span className="satir-baslik" lang={cevrilmedi ? 'en' : 'tr'}>
          {trBaslik || metin(kayit.original_title)}
        </span>
        {(rozetler.length > 0 || cevrilmedi || kayit.translation_provider) && (
          <span className="satir-rozetler">
            {rozetler.map((r, i) => <span key={i} className={`rozet ${r.tur}`}>{r.metin}</span>)}
            <CeviriEtiketi kayit={kayit} className="" />
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

// Filtre/eylem cubugu: donem, siralama, kaynak acilir menusu, bolume ozgu ek filtre (ekFiltre),
// Yenile, HTML rapor, onbellegi temizle, Cek. Donem ve kaynaklar hem listeyi suzer hem Cek'i belirler
// (Cek en fazla 15 gun). Cek suresince dugme doner (eski tam ekran bekleme penceresi yok); HTML rapor
// hazirlanirken (raporHazirlaniyor) rapor dugmesi devre disi. Ozelliklerin cogu hooks/useBolumVerisi
// cubukOzellikleri'nden gelir.
// gun: sayi ya da null (Tumu); gunSecenekleri: secenekler.js DONEM_SECENEKLERI;
// siralaSecenekleri: [{deger, etiket}] (secenekler.js SIRALA_SECENEKLERI, Zafiyetler'de + CVSS).
export function BolumCubugu({
  kimlik, gun, gunSecenekleri, onGunDegis,
  sirala, siralaSecenekleri, onSiralaDegis,
  kaynaklar, seciliKaynaklar, onKaynakDegis, kaynakSayilari = {},
  ekFiltre = null,
  yukleniyor, cekiliyor, raporHazirlaniyor = false, onYenile, onRapor, onTemizle, onCek,
}) {
  const seciliSayisi = kaynaklar.filter(k => seciliKaynaklar[k.value]).length
  // Secenekler disinda veritabaninda kaydi kalan kaynaklar (or. 2026-10-14'te cikarilan kaynaklar)
  const digerKaynaklar = Object.entries(kaynakSayilari).filter(([ad]) => !kaynaklar.some(k => k.value === ad))
  // Bu bolumde olmayan siralama (or. adresten sirala=cvss) sunucuda varsayilana duser; ayni gorunur
  const gecerliSirala = siralaSecenekleri.some(s => s.deger === sirala) ? sirala : siralaSecenekleri[0].deger

  return (
    <section className="filtre-cubugu cam-kart" aria-label="Filtreler ve eylemler">
      <div className="filtre-gruplari">
        <label className="filtre-grubu">
          <span className="filtre-etiketi">Dönem</span>
          <Form.Select
            size="sm"
            className="cubuk-secim"
            value={gun ?? TUMU_DEGERI}
            onChange={(e) => onGunDegis(e.target.value === TUMU_DEGERI ? null : Number(e.target.value))}
            aria-label="Dönem"
          >
            {gunSecenekleri.map(g => (
              <option key={g ?? TUMU_DEGERI} value={g ?? TUMU_DEGERI}>{donemEtiketi(g)}</option>
            ))}
          </Form.Select>
        </label>

        <label className="filtre-grubu">
          <span className="filtre-etiketi">Sırala</span>
          <Form.Select
            size="sm"
            className="cubuk-secim"
            value={gecerliSirala}
            onChange={(e) => onSiralaDegis(e.target.value)}
            aria-label="Sırala"
          >
            {siralaSecenekleri.map(s => <option key={s.deger} value={s.deger}>{s.etiket}</option>)}
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
              const secili = !!seciliKaynaklar[kaynak.value]
              return (
                <Form.Check
                  key={kaynak.id}
                  type="checkbox"
                  id={kaynak.id}
                  className="kaynak-secenegi"
                  checked={secili}
                  // Bos kaynak secimi "hepsi" demek: son secili kaynak kaldirilamaz
                  disabled={secili && seciliSayisi === 1}
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
        <button
          type="button"
          className="cubuk-dugme"
          onClick={onRapor}
          disabled={raporHazirlaniyor}
          aria-busy={raporHazirlaniyor}
          title="Kayıtları HTML rapor olarak indir"
        >
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
          title={`Seçili kaynaklardan son ${cekimGunu(gun)} günün kayıtlarını çek`}
        >
          {cekiliyor
            ? <><Spinner size="sm" aria-hidden="true" />Çekiliyor…</>
            : <><FaDownload aria-hidden="true" />Çek</>}
        </button>
      </div>
    </section>
  )
}

// cubuk: oge ya da ({ kapat }) => oge. Islev bicimi bolume okuma panelini kapatma yolu verir
// (or. onbellek temizlenince; secili kayit listeden dusse de panel acik kalir, bkz. useSeciliKayit).
// toplam/sayfa/sayfaSayisi/boyut/guncel: useListeSorgusu'ndan; gun: sayi ya da null (Tumu); onSayfa(n).
export default function BolumSayfasi({
  bolum, baslik, kayitlar, yukleniyor, cubuk,
  istatistik = null, dagilim = [],
  toplam = kayitlar.length, sayfa = 1, sayfaSayisi = 1, boyut = 25, gun = null, onSayfa = () => {},
  guncel = true,
}) {
  // Secim tum liste uzerinden cozulur: periyodik yenileme, sayfa ya da filtre degisikligi acik paneli kapatmaz
  const { secili, sec, kapat } = useSeciliKayit(kayitlar)
  const okumaKaydi = useMemo(() => (secili ? haberOkumaKaydi(secili, bolum) : null), [secili, bolum])
  // Yeni sorgu yuklenirken ya da hatayla bittiyse (guncel degil) eski sorgunun toplami yeni
  // donem/sayfayla karismasin: sayim satiri ve sayfa cubugu gosterilmez
  const sonucVar = guncel && !yukleniyor && kayitlar.length > 0

  let liste
  if (yukleniyor) {
    liste = <p className="liste-bos">Kayıtlar yükleniyor…</p>
  } else if (kayitlar.length === 0) {
    liste = (
      <p className="liste-bos">
        {istatistik && Number(istatistik.total) > 0
          ? 'Bu filtreyle eşleşen kayıt bulunamadı.'
          : 'Liste boş. Kayıt almak için "Çek" düğmesini kullanın.'}
      </p>
    )
  } else {
    liste = (
      <ul className="oncelikli-liste">
        {kayitlar.map(kayit => (
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

      {typeof cubuk === 'function' ? cubuk({ kapat }) : cubuk}

      <p className="liste-sayaci" aria-live="polite">
        {sonucVar ? sayimMetni({ gun, toplam, sayfa, boyut, adet: kayitlar.length }) : ''}
      </p>

      {liste}

      {sonucVar && <SayfaCubugu sayfa={sayfa} sayfaSayisi={sayfaSayisi} onSayfa={onSayfa} />}

      <OkumaPaneli kayit={okumaKaydi} onKapat={kapat} />
    </div>
  )
}

// Bolum hata uyarisi (sag ustte, kapatilabilir); metin yoksa hicbir sey cizmez
export function HataUyarisi({ metin, onKapat }) {
  if (!metin) return null
  return (
    <Alert
      variant="danger"
      className="position-fixed top-0 end-0 m-3"
      style={{ zIndex: 9999, minWidth: '300px' }}
      dismissible
      onClose={onKapat}
    >
      {metin}
    </Alert>
  )
}
