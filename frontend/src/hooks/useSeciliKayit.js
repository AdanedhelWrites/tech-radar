import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'

// Bolum sayfalarinda okuma panelinde acik kayit (spec 2026-10-31 §6): secim ?kayit=<id> sorgu
// parametresinde tutulur; adres paylasilabilir, geri tusu paneli kapatir. Secili kayit her
// render'da id ile listeden cozulur: periyodik yenileme yeni nesneler getirse de panel kapanmaz.
// 2026-11-05 (filtre/sayfalama spec G4): liste artik tek sayfa; sayfa, filtre degisimi ya da 5 sn
// yenilemesi secili kaydi listeden dusurebilir. Panel o zaman son bilinen nesneyle acik kalir,
// yalniz kapat() (ya da geri tusu) kapatir.
// 2026-11-07: listede hic gorulmemis id (baska sayfa, filtre disi ya da eski kayit; paylasilan adres)
// tekilGetir(id) ile sunucudan istenir. Kayit yoksa (silinmis, elle yazilmis) "Kayit bulunamadi"
// bildirimi cikar ve parametre adresten silinir; once bu kayitlar sessizce hic acilmiyordu.

const PARAMETRE = 'kayit'
const BULUNAMADI = 'Kayıt bulunamadı: silinmiş ya da saklama süresi dolmuş olabilir.'

// tekilGetir(id) -> Promise<kayit|null> (istege bagli); hazir: liste ilk yanitini aldi (yuklenirken istenmez,
// kayit cogu zaman ilk sayfadadir)
export default function useSeciliKayit(kayitlar, tekilGetir = null, hazir = true) {
  const [parametreler, setParametreler] = useSearchParams()
  const { state, key } = useLocation()
  const navigate = useNavigate()
  // Kapatilan gecmis girisinin anahtari: Offcanvas onHide, popstate islenmeden iki kez gelebilir
  // (Esc + kapat dugmesi); ikinci cagri ikinci kez geri gidip sayfadan cikmamali (karar R12).
  // Her secim yeni bir giris (yeni anahtar) acar, boylece ayni kayit yeniden acilip kapatilabilir.
  const kapatilanGiris = useRef(null)
  // Secili id'nin listede en son goruldugu hali; baska id secilince kullanilmaz
  const sonBilinen = useRef(null)
  // Sunucudan istenen tekil kayit: { id, kayit } (kayit null: bulunamadi)
  const [uzak, setUzak] = useState(null)

  const deger = parametreler.get(PARAMETRE)
  const id = deger ? Number(deger) : NaN
  const gecerli = Number.isFinite(id)
  const bulunan = gecerli ? (kayitlar || []).find(k => k.id === id) ?? null : null
  if (bulunan) sonBilinen.current = bulunan
  const uzaktan = uzak?.id === id ? uzak.kayit : null
  if (!bulunan && uzaktan && sonBilinen.current?.id !== id) sonBilinen.current = uzaktan
  const secili = bulunan ?? (sonBilinen.current?.id === id ? sonBilinen.current : null)

  const istenecek = gecerli && !secili && tekilGetir && hazir && uzak?.id !== id ? id : null
  useEffect(() => {
    if (istenecek === null) return undefined
    let iptal = false
    tekilGetir(istenecek)
      .then(kayit => { if (!iptal) setUzak({ id: istenecek, kayit: kayit ?? null }) })
      // Ag hatasi "bulunamadi" sayilmaz (kayit: undefined): bildirim cikmaz, parametre yerinde kalir
      .catch(() => { if (!iptal) setUzak({ id: istenecek, kayit: undefined }) })
    return () => { iptal = true }
  }, [istenecek, tekilGetir])

  const bulunamadi = gecerli && uzak?.id === id && uzak.kayit === null && !secili
  useEffect(() => {
    if (!bulunamadi) return
    toast.error(BULUNAMADI, { id: 'kayit-bulunamadi' })
    setParametreler(onceki => {
      const sonraki = new URLSearchParams(onceki)
      sonraki.delete(PARAMETRE)
      return sonraki
    }, { replace: true })
  }, [bulunamadi, setParametreler])

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
