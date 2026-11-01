// Son ziyaret zamani. Gizli pencerede localStorage hata firlatabilir: okuma null, yazma sessiz gecer.
const ANAHTAR = 'tr.sonZiyaret'

export const sonZiyaretOku = () => {
  try {
    return localStorage.getItem(ANAHTAR)
  } catch {
    return null
  }
}

export const sonZiyaretYaz = (iso) => {
  try {
    localStorage.setItem(ANAHTAR, iso)
  } catch {
    // yazilamazsa ana sayfa yine acilir
  }
}

// Sekme basina taban (karar R9): sayfa gizlenince/F5'te (pagehide) son ziyaret en yeni kayda
// ilerler; taban sessionStorage'da sabit kalir, boylece yenileme "Yeni" rozetlerini silmez.
// Gunlerce acik sekmede taban hic ilerlemesin diye omru vardir: CVE cekim dongusu kadar (6 sa)
// sonra bir sonraki okumada son ziyarete ilerler. Ilk ziyarette (localStorage bos) taban yazilmaz.
const TABAN_ANAHTARI = 'tr.sonZiyaretTaban'
const TABAN_ZAMANI_ANAHTARI = 'tr.sonZiyaretTabanZamani'
export const TABAN_OMRU_MS = 6 * 60 * 60 * 1000

const oturumOku = (anahtar) => {
  try {
    return sessionStorage.getItem(anahtar)
  } catch {
    return null
  }
}

const oturumYaz = (anahtar, deger) => {
  try {
    sessionStorage.setItem(anahtar, deger)
  } catch {
    // sessionStorage yoksa taban her yuklemede localStorage'dan okunur
  }
}

export const ziyaretTabani = (simdi = Date.now()) => {
  const taban = oturumOku(TABAN_ANAHTARI)
  // Kurulma zamani olmayan (eski bicim) taban suresi dolmus sayilir
  const kuruldu = Number(oturumOku(TABAN_ZAMANI_ANAHTARI)) || 0
  if (taban != null && simdi - kuruldu < TABAN_OMRU_MS) return taban
  const sonZiyaret = sonZiyaretOku()
  if (sonZiyaret != null) {
    oturumYaz(TABAN_ANAHTARI, sonZiyaret)
    oturumYaz(TABAN_ZAMANI_ANAHTARI, String(simdi))
  }
  return sonZiyaret ?? taban
}
