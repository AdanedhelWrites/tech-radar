import { useEffect, useRef } from 'react'

// Belirli aralikla yeniler; sekme arka plandayken (document.hidden) istek atmaz,
// one donunce hemen bir kez yeniler. 2026-10-08: alti bolum sayfasi 5 sn'de bir
// sinirsiz polling yapiyordu; arka planda acik kalan sekmeler API'ye bosa yuk bindiriyordu.
export default function useAraliklaYenile(callback, ms) {
  const sonCallback = useRef(callback)
  useEffect(() => {
    sonCallback.current = callback
  })

  useEffect(() => {
    const tik = () => {
      if (!document.hidden) sonCallback.current()
    }
    const id = setInterval(tik, ms)
    document.addEventListener('visibilitychange', tik)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', tik)
    }
  }, [ms])
}
