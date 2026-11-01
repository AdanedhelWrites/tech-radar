import { useCallback, useEffect, useRef, useState } from 'react'
import { ozetApi, newsApi, k8sApi, sreApi, devtoolsApi, aiApi } from '../../services/api'
import useAraliklaYenile from '../../hooks/useAraliklaYenile'
import { sonZiyaretOku, sonZiyaretYaz } from '../../utils/sonZiyaret'
import useZiyaretTabani from '../../hooks/useZiyaretTabani'
import { gundemBirlestir } from '../../utils/gundem'
import { goreliZaman } from '../../utils/zaman'
import SaglikSeridi from '../SaglikSeridi'
import OkumaPaneli from '../okuma/OkumaPaneli'
import DurumOzeti from './DurumOzeti'
import CvssGrafigi from './CvssGrafigi'
import OncelikliListe from './OncelikliListe'
import Gundem from './Gundem'

// Genel Bakis (ana sayfa, spec 2026-10-31 G3): zafiyet durumu ozeti, CVSS dagilimi, oncelikli
// zafiyetler ve diger bes bolumden gundem. Ozet sayilari yalniz /api/ozet/'ten gelir (spec §5).

const YENILEME_MS = 5 * 60 * 1000
const GUNDEM_ADEDI = 6
const GUNDEM_UCLARI = [
  { bolum: 'news', getir: () => newsApi.getNews() },
  { bolum: 'kubernetes', getir: () => k8sApi.getK8s() },
  { bolum: 'sre', getir: () => sreApi.getSRE() },
  { bolum: 'devtools', getir: () => devtoolsApi.getDevTools() },
  { bolum: 'ai', getir: () => aiApi.getAINews() },
]

const zamanDamgasi = (iso) => {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : t
}

// Listelerdeki en yeni created_at (ISO, API'nin yazdigi bicimde). Yoksa null.
const enYeniZaman = (kayitlar) => kayitlar.reduce((enYeni, kayit) => {
  const t = zamanDamgasi(kayit?.created_at)
  return t != null && (enYeni == null || t > zamanDamgasi(enYeni)) ? kayit.created_at : enYeni
}, null)

const saatDakika = (iso) => {
  const t = zamanDamgasi(iso)
  if (t == null) return '-'
  const d = new Date(t)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function GenelBakis() {
  // Sekme tabani (karar R9): periyodik yenileme de F5 de ayni degeri kullanir, "Yeni" rozetleri ve
  // "son ziyaretinizden" cumlesi silinmez; omru dolunca sekmeye donuldugunde ilerler
  const sonZiyaret = useZiyaretTabani()
  const [ozet, setOzet] = useState(null)
  const [ozetHata, setOzetHata] = useState(false)
  const [gundem, setGundem] = useState(null)
  const [gundemHata, setGundemHata] = useState(false)
  const [secili, setSecili] = useState(null)
  const enYeniRef = useRef(null)

  const ozetYukle = useCallback(async () => {
    try {
      const yanit = await ozetApi.getOzet(sonZiyaret ?? undefined)
      setOzet(yanit.data)
      setOzetHata(false)
    } catch {
      setOzetHata(true)
    }
  }, [sonZiyaret])

  const gundemYukle = useCallback(async () => {
    // Bir bolumun hatasi digerlerini dusurmez; hepsi hata verirse gundem hata gosterir
    const sonuclar = await Promise.allSettled(GUNDEM_UCLARI.map(u => u.getir()))
    if (sonuclar.every(s => s.status === 'rejected')) {
      setGundemHata(true)
      return
    }
    const listeler = sonuclar.map((s, i) => {
      const kayitlar = s.status === 'fulfilled' ? s.value?.data?.data : null
      return { bolum: GUNDEM_UCLARI[i].bolum, kayitlar: Array.isArray(kayitlar) ? kayitlar : [] }
    })
    setGundem(gundemBirlestir(listeler, GUNDEM_ADEDI))
    setGundemHata(false)
  }, [])

  const yukle = useCallback(() => {
    ozetYukle()
    gundemYukle()
  }, [ozetYukle, gundemYukle])

  useEffect(() => { yukle() }, [yukle])
  useAraliklaYenile(yukle, YENILEME_MS)

  // Son ziyaret degeri: oncelikli liste ve gundemdeki en yeni created_at (spec §6)
  useEffect(() => {
    enYeniRef.current = enYeniZaman([...(ozet?.priority || []), ...(gundem || []).map(g => g.kayit)])
  }, [ozet, gundem])

  useEffect(() => {
    const yaz = () => {
      const enYeni = enYeniRef.current
      if (!enYeni) return
      // Kayitli deger daha yeniyse (baska sekme) geri alinmaz
      const kayitli = zamanDamgasi(sonZiyaretOku())
      if (kayitli == null || zamanDamgasi(enYeni) > kayitli) sonZiyaretYaz(enYeni)
    }
    const gorunurlukDegisti = () => {
      if (document.visibilityState === 'hidden') yaz()
    }
    document.addEventListener('visibilitychange', gorunurlukDegisti)
    window.addEventListener('pagehide', yaz)
    return () => {
      document.removeEventListener('visibilitychange', gorunurlukDegisti)
      window.removeEventListener('pagehide', yaz)
    }
  }, [])

  const kapat = useCallback(() => setSecili(null), [])
  // Ozet alinamazsa grafik gosterilmez: bos halkalar "zafiyet yok" gibi okunmamali
  const grafikVar = !ozetHata

  return (
    <div className="genel-bakis">
      <section className={grafikVar ? 'genel-kafa' : 'genel-kafa grafiksiz'}>
        <DurumOzeti ozet={ozet} hata={ozetHata} />
        {grafikVar && <CvssGrafigi noktalar={ozet?.chart || []} skorsuz={ozet?.unscored_count || 0} />}
      </section>

      <div className="genel-izgara">
        <OncelikliListe
          kayitlar={ozet?.priority || null}
          hata={ozetHata}
          sonZiyaret={sonZiyaret}
          onSec={setSecili}
        />
        <Gundem ogeler={gundem} hata={gundemHata} onSec={setSecili} />
      </div>

      <div className="genel-alt">
        <SaglikSeridi />
        {ozet?.fetch && !ozetHata && (
          <span className="cekim-bilgisi">
            {[
              ozet.fetch.last_success_at && `Son güncelleme ${goreliZaman(ozet.fetch.last_success_at)}`,
              `Sonraki çekim ${saatDakika(ozet.fetch.next_at)}`,
            ].filter(Boolean).join(' · ')}
          </span>
        )}
      </div>

      <OkumaPaneli kayit={secili} onKapat={kapat} />
    </div>
  )
}
