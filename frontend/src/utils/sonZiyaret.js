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
