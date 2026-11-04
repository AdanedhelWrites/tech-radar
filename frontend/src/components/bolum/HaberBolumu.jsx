import toast from 'react-hot-toast'
import { useCallback, useEffect, useState } from 'react'
import { Alert } from 'react-bootstrap'
import useListeSorgusu from '../../hooks/useListeSorgusu'
import { istekHataMesaji } from '../../services/api'
import { raporHtml, raporIndir, raporKayitlariniGetir } from '../../utils/rapor'
import BolumSayfasi, { BolumCubugu } from './BolumSayfasi'
import { DONEM_SECENEKLERI, SIRALA_SECENEKLERI, cekimGunu, donemEtiketi } from './secenekler'

// Bes haber bolumunun (Siber Guvenlik, Kubernetes, SRE, DevTools, Yapay Zeka) veri ve eylem katmani
// (spec 2026-11-05 G1): liste useListeSorgusu ile sunucuda suzulur, siralanir ve sayfalanir
// (adreste tutulur, 5 sn'de bir sessizce yenilenir); istatistik, Cek, temizleme ve HTML rapor
// burada bir kez yazilir. Bolum bilesenleri yalniz bolume ozgu tanimi (tanim) verir:
//   bolum, baslik, kimlik, kaynaklar: [{id, name, value, icon}]
//   api: { liste(params), cek({days, sources}), temizle(), istatistik() }
//   metinler: { yuklemeHatasi, cekimHatasi, temizleOnayi }
//   rapor: utils/rapor raporHtml secenekleri + dosyaOnEki
//   istege bagli: dagilim(istatistik) -> [[etiket, adet]], ekAnahtarlar: ['kategori'],
//                 ekFiltre({ sorgu, degistir }) -> filtre cubuguna eklenen oge

const YONETICI_GEREKLI = 'Sıfırlama için yönetici girişi gerekli: önce Django admin (/admin) üzerinden oturum açın.'

export default function HaberBolumu({ tanim }) {
  const {
    bolum, baslik, kimlik, kaynaklar, api, metinler, rapor,
    dagilim = null, ekAnahtarlar = [], ekFiltre = null,
  } = tanim
  const liste = useListeSorgusu({ getir: api.liste, ekAnahtarlar })
  const { sorgu, degistir } = liste

  const [istatistik, setIstatistik] = useState({ total: 0, by_source: {}, last_update: null })
  const [cekiliyor, setCekiliyor] = useState(false)
  const [hata, setHata] = useState(null)
  // Kullanicinin kapattigi liste hatasi (hook'un hatasi yeni istek baslayinca kendiliginden temizlenir)
  const [kapatilanListeHatasi, setKapatilanListeHatasi] = useState(null)

  const istatistikYukle = useCallback(async () => {
    try {
      const yanit = await api.istatistik()
      if (yanit.data.success) setIstatistik(yanit.data)
    } catch (err) {
      console.error('Stats yüklenirken hata:', err)
    }
  }, [api])

  useEffect(() => {
    istatistikYukle()
  }, [istatistikYukle])

  // Kaynak secimi adreste: bos = hepsi. Liste de Cek de ayni kumeyi kullanir.
  const tumKaynaklar = kaynaklar.map(k => k.value)
  const seciliDegerler = sorgu.kaynak.length ? tumKaynaklar.filter(v => sorgu.kaynak.includes(v)) : tumKaynaklar
  const seciliKaynaklar = Object.fromEntries(tumKaynaklar.map(v => [v, seciliDegerler.includes(v)]))

  const kaynakDegis = (deger) => {
    const yeni = seciliDegerler.includes(deger)
      ? seciliDegerler.filter(v => v !== deger)
      : tumKaynaklar.filter(v => v === deger || seciliDegerler.includes(v))
    if (yeni.length === 0) return
    degistir({ kaynak: yeni.length === tumKaynaklar.length ? [] : yeni })
  }

  const cek = async () => {
    if (seciliDegerler.length === 0) {
      setHata('Lütfen en az bir kaynak seçin!')
      return
    }
    try {
      setCekiliyor(true)
      setHata(null)
      const yanit = await api.cek({ days: cekimGunu(sorgu.gun), sources: seciliDegerler })
      if (yanit.data.success) {
        istatistikYukle()
        toast.success('Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.', { icon: '🚀', duration: 4000 })
      } else {
        setHata(yanit.data.message)
      }
    } catch (err) {
      setHata(istekHataMesaji(err, metinler.cekimHatasi))
    } finally {
      setCekiliyor(false)
    }
  }

  // kapat: BolumSayfasi'nin okuma paneli. Liste bosalsa da panel son bilinen kayitla acik kalacagi
  // icin (useSeciliKayit) temizlik sonrasi acikca kapatilir ve liste yeniden istenir.
  const temizle = async (kapat) => {
    if (!window.confirm(metinler.temizleOnayi)) return
    try {
      await api.temizle()
      kapat()
      liste.yenile()
      istatistikYukle()
      toast.success('Veriler başarıyla temizlendi', { icon: '🗑️' })
    } catch (err) {
      setHata(err.response?.status === 403 ? YONETICI_GEREKLI : 'Sıfırlama sırasında hata oluştu')
    }
  }

  const raporAl = async () => {
    try {
      const { kayitlar, toplam } = await raporKayitlariniGetir(api.liste, liste.istek)
      const siralama = SIRALA_SECENEKLERI.find(s => s.deger === sorgu.sirala) ?? SIRALA_SECENEKLERI[0]
      const aciklama = `${donemEtiketi(sorgu.gun)} · ${siralama.etiket}`
      raporIndir(raporHtml({ ...rapor, aciklama, kayitlar, toplam }), rapor.dosyaOnEki)
    } catch (err) {
      console.error(err)
      setHata('Dışarı aktarma hatası')
    }
  }

  const listeHatasi = liste.hata && liste.hata !== kapatilanListeHatasi ? metinler.yuklemeHatasi : null
  const gorunenHata = hata || listeHatasi
  const hatayiKapat = () => {
    if (hata) setHata(null)
    else setKapatilanListeHatasi(liste.hata)
  }

  return (
    <>
      <BolumSayfasi
        bolum={bolum}
        baslik={baslik}
        kayitlar={liste.kayitlar}
        yukleniyor={liste.yukleniyor}
        istatistik={istatistik}
        dagilim={dagilim ? dagilim(istatistik) : []}
        toplam={liste.toplam}
        sayfa={liste.sayfa}
        sayfaSayisi={liste.sayfaSayisi}
        boyut={liste.boyut}
        gun={sorgu.gun}
        onSayfa={liste.sayfayaGit}
        cubuk={({ kapat }) => (
          <BolumCubugu
            kimlik={kimlik}
            gun={sorgu.gun}
            gunSecenekleri={DONEM_SECENEKLERI}
            onGunDegis={(gun) => degistir({ gun })}
            sirala={sorgu.sirala}
            siralaSecenekleri={SIRALA_SECENEKLERI}
            onSiralaDegis={(sirala) => degistir({ sirala })}
            kaynaklar={kaynaklar}
            seciliKaynaklar={seciliKaynaklar}
            onKaynakDegis={kaynakDegis}
            kaynakSayilari={istatistik.by_source}
            ekFiltre={ekFiltre ? ekFiltre({ sorgu, degistir }) : null}
            yukleniyor={liste.yukleniyor}
            cekiliyor={cekiliyor}
            onYenile={() => liste.yenile()}
            onRapor={raporAl}
            onTemizle={() => temizle(kapat)}
            onCek={cek}
          />
        )}
      />

      {gorunenHata && (
        <Alert
          variant="danger"
          className="position-fixed top-0 end-0 m-3"
          style={{ zIndex: 9999, minWidth: '300px' }}
          dismissible
          onClose={hatayiKapat}
        >
          {gorunenHata}
        </Alert>
      )}
    </>
  )
}
