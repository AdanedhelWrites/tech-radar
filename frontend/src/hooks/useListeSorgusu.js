import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import useAraliklaYenile from './useAraliklaYenile'

// Bolum listelerinin sunucu tarafi sorgusu (spec 2026-11-05 G4): donem, siralama, kaynak, bolume
// ozgu ek filtreler (onem, kategori) ve sayfa adreste tutulur; geri tusu ve sayfa yenileme ayni
// gorunume doner. Varsayilan degerler adrese yazilmaz, Tumu ise ?gun=tumu ile acikca tutulur.
// Filtre ya da siralama degisince sayfa silinir (1'e doner). Liste 5 sn'de bir sessizce yenilenir:
// sayfa, adres ve yukleniyor degismez (acik okuma paneli de kapanmaz, bkz. useSeciliKayit).

export const GUN_SECENEKLERI = [1, 3, 7, 14, 30]
export const VARSAYILAN_GUN = 7
export const SAYFA_BOYUTU = 25
const VARSAYILAN_SIRALA = 'yeni'
const SIRALAMALAR = ['yeni', 'eski', 'cvss']
const TUMU = 'tumu'
const YENILEME_MS = 5000

// Adresten gelen bozuk degerler varsayilana duser (sunucu da ayni kurali uygular)
const gunOku = (ham) => {
  if (ham === TUMU) return null
  const gun = Number(ham)
  return ham && GUN_SECENEKLERI.includes(gun) ? gun : VARSAYILAN_GUN
}

const sayfaOku = (ham) => {
  const sayfa = Number(ham)
  return Number.isInteger(sayfa) && sayfa >= 1 ? sayfa : 1
}

const siralaOku = (ham) => (SIRALAMALAR.includes(ham) ? ham : VARSAYILAN_SIRALA)

// bilinenler: bolumun kaynak listesi (verilirse). Listede olmayan adres degerleri atilir: istege ve
// Cek'e yalniz secenek listesindeki adlar gider; hepsi bilinmiyorsa secim bos (= butun kaynaklar) kalir.
const kaynakOku = (ham, bilinenler) => {
  const adlar = ham ? ham.split(',').filter(Boolean) : []
  return bilinenler ? adlar.filter(ad => bilinenler.includes(ad)) : adlar
}

// Tek bir sorgu alanini adrese yazar; varsayilan ya da bos deger parametreyi siler
const adreseYaz = (parametreler, ad, deger) => {
  let yazilacak
  if (ad === 'gun') {
    yazilacak = deger === null ? TUMU : (deger === VARSAYILAN_GUN ? '' : String(deger ?? ''))
  } else if (ad === 'sirala') {
    yazilacak = deger === VARSAYILAN_SIRALA ? '' : (deger ?? '')
  } else if (ad === 'kaynak') {
    yazilacak = Array.isArray(deger) ? deger.join(',') : (deger ?? '')
  } else {
    yazilacak = deger == null ? '' : String(deger)
  }
  if (yazilacak) parametreler.set(ad, yazilacak)
  else parametreler.delete(ad)
}

// kaynaklar: bolumun bilinen kaynak adlari (istege bagli; verilmezse adres degerleri suzulmez)
export default function useListeSorgusu({ getir, ekAnahtarlar = [], kaynaklar = null }) {
  const [parametreler, setParametreler] = useSearchParams()
  // Cagiran her render'da yeni dizi gecebilir; anahtar metniyle sabitlenir (kaynak adlarinda virgul yok)
  const ekAnahtarMetni = ekAnahtarlar.join(',')
  const kaynakMetni = kaynaklar ? kaynaklar.join(',') : null

  const sorgu = useMemo(() => {
    const sonuc = {
      gun: gunOku(parametreler.get('gun')),
      sirala: siralaOku(parametreler.get('sirala')),
      kaynak: kaynakOku(parametreler.get('kaynak'), kaynakMetni === null ? null : kaynakMetni.split(',')),
    }
    for (const ad of ekAnahtarMetni.split(',').filter(Boolean)) {
      sonuc[ad] = parametreler.get(ad) || ''
    }
    return sonuc
  }, [parametreler, ekAnahtarMetni, kaynakMetni])
  const istenenSayfa = sayfaOku(parametreler.get('sayfa'))

  // API parametreleri: gun (Tumu disinda) ve varsayilanlar her zaman, bos filtreler hic gonderilmez.
  // Metin anahtar yalniz sorgu degisince degisir (?kayit= gibi ilgisiz parametreler istek atmaz).
  const istekAnahtari = useMemo(() => {
    const istek = {}
    if (sorgu.gun !== null) istek.gun = sorgu.gun
    istek.sirala = sorgu.sirala
    istek.sayfa = istenenSayfa
    istek.boyut = SAYFA_BOYUTU
    if (sorgu.kaynak.length) istek.kaynak = sorgu.kaynak.join(',')
    for (const ad of ekAnahtarMetni.split(',').filter(Boolean)) {
      if (sorgu[ad]) istek[ad] = sorgu[ad]
    }
    return JSON.stringify(istek)
  }, [sorgu, istenenSayfa, ekAnahtarMetni])
  // Gecerli istek parametreleri; disari da verilir (rapor ayni filtre ve siralamayla kendi sayfalarini ister)
  const istek = useMemo(() => JSON.parse(istekAnahtari), [istekAnahtari])

  const [sonuc, setSonuc] = useState({
    anahtar: null, kayitlar: [], toplam: 0, sayfa: 1, sayfaSayisi: 1, boyut: SAYFA_BOYUTU,
  })
  const [yukleniyor, setYukleniyor] = useState(true)
  const [hata, setHata] = useState(null)

  const getirRef = useRef(getir)
  useEffect(() => {
    getirRef.current = getir
  })
  // Her istek bir numara alir; yalniz en son istegin yaniti uygulanir (gec gelen eski yanit
  // yeni sorgunun listesini ezmez). bekleyen: yanit beklenirken sessiz yenileme istek yigmaz.
  const sonIstek = useRef(0)
  const bekleyen = useRef(false)

  const yukle = useCallback(async (sessiz = false) => {
    const no = ++sonIstek.current
    bekleyen.current = true
    if (!sessiz) {
      setYukleniyor(true)
      // Yeni sorgu basladi: onceki sorgunun hatasi yanit beklenirken asili kalmaz
      setHata(null)
    }
    try {
      const yanit = await getirRef.current(istek)
      if (no !== sonIstek.current) return
      const veri = yanit.data
      if (!veri?.success) {
        // Basarisiz zarf (success: false) da hatadir; sessiz yenilemede ekran bozulmaz
        if (!sessiz) setHata(new Error(veri?.message || 'Liste yanıtı başarısız'))
      } else {
        const kayitlar = veri.data || []
        setSonuc({
          anahtar: istekAnahtari,
          kayitlar,
          toplam: veri.toplam ?? kayitlar.length,
          sayfa: veri.sayfa ?? istek.sayfa,
          sayfaSayisi: veri.sayfa_sayisi ?? 1,
          boyut: veri.boyut ?? SAYFA_BOYUTU,
        })
        setHata(null)
      }
    } catch (err) {
      if (no !== sonIstek.current) return
      // Sessiz yenilemenin hatasi ekrandaki listeyi ve durumu bozmaz
      if (!sessiz) setHata(err)
      console.error(err)
    } finally {
      if (no === sonIstek.current) {
        bekleyen.current = false
        setYukleniyor(false)
      }
    }
  }, [istek, istekAnahtari])

  useEffect(() => {
    yukle()
  }, [yukle])

  // Sekme arka plandayken durur (hooks/useAraliklaYenile)
  useAraliklaYenile(() => {
    if (!bekleyen.current) yukle(true)
  }, YENILEME_MS)

  const yenile = useCallback(() => yukle(), [yukle])

  const degistir = useCallback((kismi) => {
    setParametreler(onceki => {
      const sonraki = new URLSearchParams(onceki)
      for (const [ad, deger] of Object.entries(kismi)) adreseYaz(sonraki, ad, deger)
      sonraki.delete('sayfa')
      return sonraki
    })
  }, [setParametreler])

  const sayfayaGit = useCallback((sayfa) => {
    setParametreler(onceki => {
      const sonraki = new URLSearchParams(onceki)
      if (sayfa > 1) sonraki.set('sayfa', String(sayfa))
      else sonraki.delete('sayfa')
      return sonraki
    })
  }, [setParametreler])

  // guncel: eldeki yanit gecerli sorguya ait. Degilse (ilk yanittan once, yeni sorgu beklenirken ya da
  // yeni sorgu hatayla bittiyse) toplam/sayfaSayisi eski sorgunundur: sayim satiri ve sayfa cubugu
  // yalniz guncel iken gosterilmeli. Sayfa: guncelse sunucunun (asiri sayfa son sayfaya cekilir), degilse istenen.
  const guncel = sonuc.anahtar === istekAnahtari
  return {
    istek,
    guncel,
    kayitlar: sonuc.kayitlar,
    toplam: sonuc.toplam,
    sayfa: guncel ? sonuc.sayfa : istenenSayfa,
    sayfaSayisi: sonuc.sayfaSayisi,
    boyut: sonuc.boyut,
    yukleniyor,
    hata,
    sorgu,
    degistir,
    sayfayaGit,
    yenile,
  }
}
