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
// ilerler; taban sessionStorage'da sekme acik kaldikca sabit kalir, boylece yenileme "Yeni"
// rozetlerini silmez. Ilk ziyarette (localStorage bos) taban yazilmaz.
const TABAN_ANAHTARI = 'tr.sonZiyaretTaban'

const tabanOku = () => {
  try {
    return sessionStorage.getItem(TABAN_ANAHTARI)
  } catch {
    return null
  }
}

const tabanYaz = (iso) => {
  try {
    sessionStorage.setItem(TABAN_ANAHTARI, iso)
  } catch {
    // sessionStorage yoksa taban her yuklemede localStorage'dan okunur
  }
}

export const ziyaretTabani = () => {
  const taban = tabanOku()
  if (taban != null) return taban
  const sonZiyaret = sonZiyaretOku()
  if (sonZiyaret != null) tabanYaz(sonZiyaret)
  return sonZiyaret
}
