import toast from 'react-hot-toast'
import { useCallback, useEffect, useRef, useState } from 'react'
import useListeSorgusu from './useListeSorgusu'
import { istekHataMesaji } from '../services/api'
import { raporHtml, raporIndir, raporKayitlariniGetir } from '../utils/rapor'
import { DONEM_SECENEKLERI, SIRALA_SECENEKLERI, cekimGunu, donemEtiketi } from '../components/bolum/secenekler'

// Alti bolumun (bes haber bolumu: bolum/HaberBolumu; Zafiyetler: CVEComponent) veri ve eylem katmani
// (spec 2026-11-05 G1, G4): liste useListeSorgusu ile sunucuda suzulur, siralanir, sayfalanir;
// istatistik, kaynak secimi, Cek, temizleme, HTML rapor ve hata uyarisi burada bir kez yazilir.
// tanim:
//   kaynaklar: [{id, name, value, icon}]
//   api: { liste(params), cek({days, sources}), temizle(), istatistik() }
//   metinler: { yuklemeHatasi, cekimHatasi, temizleOnayi, cekimBasladi?,
//               raporBasligi?, temizleBasligi?, cekBasligi?(gun) }  (son ucu: cubuk dugme title'lari)
//   rapor: utils/rapor raporHtml secenekleri + dosyaOnEki
//   istege bagli: ekAnahtarlar: ['kategori'], ekDegerler: { onem: [...] } (izinli ek filtre degerleri),
//                 siralaSecenekleri (varsayilan En yeni / En eski),
//                 raporAciklamaEki(sorgu) -> rapor meta satirina eklenen metin ('' = yok)

const YONETICI_GEREKLI = 'Sıfırlama için yönetici girişi gerekli: önce Django admin (/admin) üzerinden oturum açın.'
const CEKIM_BASLADI = 'Haber çekimi başladı! Haberler otomatik olarak ekrana yansıyacak.'

export default function useBolumVerisi({
  kaynaklar, api, metinler, rapor,
  ekAnahtarlar = [], ekDegerler = null, siralaSecenekleri = SIRALA_SECENEKLERI, raporAciklamaEki = null,
}) {
  const tumKaynaklar = kaynaklar.map(k => k.value)
  // Adresteki bilinmeyen kaynak adlari ve izinsiz ek filtre degerleri hook'ta atilir: liste istegi de
  // Cek de ayni kumeyi kullanir
  const liste = useListeSorgusu({ getir: api.liste, ekAnahtarlar, kaynaklar: tumKaynaklar, ekDegerler })
  const { sorgu, degistir } = liste

  const [istatistik, setIstatistik] = useState({ total: 0, by_source: {}, last_update: null })
  const [cekiliyor, setCekiliyor] = useState(false)
  const [raporHazirlaniyor, setRaporHazirlaniyor] = useState(false)
  // Durum guncellemesi beklenmeden ikinci tiklamayi da durdurur (dugme ayrica devre disi)
  const raporSuruyor = useRef(false)
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

  // Kaynak secimi adreste: bos = hepsi (sorgu.kaynak yalniz bilinen adlari icerir)
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
    try {
      setCekiliyor(true)
      setHata(null)
      const yanit = await api.cek({ days: cekimGunu(sorgu.gun), sources: seciliDegerler })
      if (yanit.data.success) {
        istatistikYukle()
        toast.success(metinler.cekimBasladi || CEKIM_BASLADI, { icon: '🚀', duration: 4000 })
      } else {
        setHata(yanit.data.message)
      }
    } catch (err) {
      setHata(istekHataMesaji(err, metinler.cekimHatasi))
    } finally {
      setCekiliyor(false)
    }
  }

  // kapat: okuma panelini kapatir. Liste bosalsa da panel son bilinen kayitla acik kalacagi icin
  // (useSeciliKayit) temizlik sonrasi acikca kapatilir ve liste yeniden istenir.
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

  // Rapor en fazla 5 istek surer: hazirlanirken ikinci tiklama yok sayilir
  const raporAl = async () => {
    if (raporSuruyor.current) return
    raporSuruyor.current = true
    setRaporHazirlaniyor(true)
    try {
      const { kayitlar, toplam } = await raporKayitlariniGetir(api.liste, liste.istek)
      const siralama = siralaSecenekleri.find(s => s.deger === sorgu.sirala) ?? siralaSecenekleri[0]
      const ek = raporAciklamaEki ? raporAciklamaEki(sorgu) : ''
      const aciklama = [donemEtiketi(sorgu.gun), siralama.etiket, ek].filter(Boolean).join(' · ')
      raporIndir(raporHtml({ ...rapor, aciklama, kayitlar, toplam }), rapor.dosyaOnEki)
    } catch (err) {
      console.error(err)
      setHata('Dışarı aktarma hatası')
    } finally {
      raporSuruyor.current = false
      setRaporHazirlaniyor(false)
    }
  }

  // Paylasilan ?kayit=<id> acik sayfada yoksa tekil kayit ayni liste ucundan istenir (useSeciliKayit).
  // Kayit yoksa null; ag hatasi firlatir.
  const listeGetir = api.liste
  const tekilGetir = useCallback(async (id) => {
    const yanit = await listeGetir({ id })
    return yanit.data?.success ? (yanit.data.data?.[0] ?? null) : null
  }, [listeGetir])

  const listeHatasi = liste.hata && liste.hata !== kapatilanListeHatasi ? metinler.yuklemeHatasi : null
  const hatayiKapat = () => {
    if (hata) setHata(null)
    else setKapatilanListeHatasi(liste.hata)
  }

  // bolum/BolumSayfasi BolumCubugu'nun ortak ozellikleri (kimlik ve ekFiltre bolumden gelir).
  // kapat: okuma panelini kapatma islevi (temizlik icin).
  const cubukOzellikleri = (kapat) => ({
    gun: sorgu.gun,
    gunSecenekleri: DONEM_SECENEKLERI,
    onGunDegis: (gun) => degistir({ gun }),
    sirala: sorgu.sirala,
    siralaSecenekleri,
    onSiralaDegis: (sirala) => degistir({ sirala }),
    kaynaklar,
    seciliKaynaklar,
    onKaynakDegis: kaynakDegis,
    ara: sorgu.ara,
    onAraDegis: (ara) => degistir({ ara }),
    kaynakSayilari: istatistik.by_source,
    yukleniyor: liste.yukleniyor,
    cekiliyor,
    raporHazirlaniyor,
    onYenile: () => liste.yenile(),
    onRapor: raporAl,
    onTemizle: () => temizle(kapat),
    onCek: cek,
    basliklar: {
      rapor: metinler.raporBasligi,
      temizle: metinler.temizleBasligi,
      cek: metinler.cekBasligi,
    },
  })

  return {
    liste,
    istatistik,
    cubukOzellikleri,
    tekilGetir,
    // Ekranda gosterilecek hata metni (eylem hatasi once) ve kapatma islevi
    hata: hata || listeHatasi,
    hatayiKapat,
  }
}
