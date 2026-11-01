import { useEffect, useState } from 'react'
import { ziyaretTabani } from '../utils/sonZiyaret'

// "Yeni" rozeti tabani (utils/sonZiyaret, karar R9). Sekme her gorunur oldugunda yeniden okunur:
// omur dolmadiysa ayni deger doner (rozetler kalir), dolduysa taban son ziyarete ilerler.
export default function useZiyaretTabani() {
  const [taban, setTaban] = useState(() => ziyaretTabani())

  useEffect(() => {
    const gorunurlukDegisti = () => {
      if (document.visibilityState === 'visible') setTaban(ziyaretTabani())
    }
    document.addEventListener('visibilitychange', gorunurlukDegisti)
    return () => document.removeEventListener('visibilitychange', gorunurlukDegisti)
  }, [])

  return taban
}
