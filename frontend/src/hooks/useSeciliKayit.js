import { useCallback, useRef } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'

// Bolum sayfalarinda okuma panelinde acik kayit (spec 2026-10-31 §6): secim ?kayit=<id> sorgu
// parametresinde tutulur; adres paylasilabilir, geri tusu paneli kapatir. Secili kayit her
// render'da id ile listeden cozulur: periyodik yenileme yeni nesneler getirse de panel kapanmaz,
// listede olmayan id (saklama suresiyle silinmis ya da elle yazilmis) null doner.

const PARAMETRE = 'kayit'

export default function useSeciliKayit(kayitlar) {
  const [parametreler, setParametreler] = useSearchParams()
  const { state, key } = useLocation()
  const navigate = useNavigate()
  // Kapatilan gecmis girisinin anahtari: Offcanvas onHide, popstate islenmeden iki kez gelebilir
  // (Esc + kapat dugmesi); ikinci cagri ikinci kez geri gidip sayfadan cikmamali (karar R12).
  // Her secim yeni bir giris (yeni anahtar) acar, boylece ayni kayit yeniden acilip kapatilabilir.
  const kapatilanGiris = useRef(null)

  const deger = parametreler.get(PARAMETRE)
  const id = deger ? Number(deger) : NaN
  const secili = Number.isFinite(id) ? (kayitlar || []).find(k => k.id === id) ?? null : null

  const sec = useCallback((yeniId) => {
    setParametreler(onceki => {
      const sonraki = new URLSearchParams(onceki)
      sonraki.set(PARAMETRE, String(yeniId))
      return sonraki
    }, parametreler.has(PARAMETRE)
      // Panel zaten aciksa gecmis buyumez: geri tusu yine panelsiz sayfaya doner
      ? { replace: true, state }
      : { state: { panelAcildi: true } })
  }, [setParametreler, parametreler, state])

  const kapat = useCallback(() => {
    if (!parametreler.has(PARAMETRE) || kapatilanGiris.current === key) return
    kapatilanGiris.current = key
    // Panel bu sayfadan acildiysa onceki giris ayni sayfanin panelsiz hali: geri gidilir, boylece
    // geri tusu paneli yeniden acmaz. Paylasilan adresle gelindiyse parametre yerinde silinir.
    if (state?.panelAcildi) {
      navigate(-1)
      return
    }
    setParametreler(onceki => {
      const sonraki = new URLSearchParams(onceki)
      sonraki.delete(PARAMETRE)
      return sonraki
    }, { replace: true })
  }, [parametreler, key, state, navigate, setParametreler])

  return { secili, sec, kapat }
}
