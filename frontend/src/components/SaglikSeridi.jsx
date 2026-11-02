import { useCallback, useEffect, useState } from 'react'
import { saglikApi } from '../services/api'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { goreliZaman } from '../utils/zaman'

// Ana sayfa saglik seridi (2026-10-14): bolum basina son basarili cekim ve sessiz kaynaklar.
// Amac: /api/v1/status/ curl rutinine bagimli kalmadan olu kaynagi arayuzde gormek.
const BOLUM_ETIKETLERI = {
  news: 'Siber Güvenlik', cve: 'CVE', kubernetes: 'Kubernetes',
  sre: 'SRE', devtools: 'DevTools', ai: 'Yapay Zeka',
}
const YENILEME_MS = 5 * 60 * 1000
// Beat 6 saatte bir cekim yapar; son basari bunun 2 kati kadar eskiyse cekim durmus demektir.
const BAYAT_SAAT = 12

export default function SaglikSeridi() {
  const [veri, setVeri] = useState(null)
  const [kuyruk, setKuyruk] = useState(null)
  const [hata, setHata] = useState(false)

  const yukle = useCallback(async () => {
    try {
      const yanit = await saglikApi.getSaglik()
      setVeri(yanit.data.sections)
      setKuyruk(yanit.data.translation_queue ?? null)
      setHata(false)
    } catch {
      setHata(true)
    }
  }, [])

  useEffect(() => { yukle() }, [yukle])
  useAraliklaYenile(yukle, YENILEME_MS)

  if (hata) return <div className="saglik-hata">Sağlık bilgisi alınamadı.</div>
  if (!veri) return null

  return (
    <div className="saglik-seridi" data-testid="saglik-seridi">
      {Object.entries(BOLUM_ETIKETLERI).map(([ad, etiket]) => {
        const b = veri[ad] || {}
        const sessiz = b.silent_sources || []
        const sorun = sessiz.length > 0 || b.last_status === 'failure'
        const veriYok = !b.last_success_at
        const bayat = !veriYok && Date.now() - Date.parse(b.last_success_at) > BAYAT_SAAT * 3600 * 1000
        const baslik = sessiz.length ? `Sessiz: ${sessiz.join(', ')}` : 'Tüm kaynaklar veri döndürüyor'
        return (
          <span key={ad} className="saglik-ogesi" title={baslik}>
            <strong>{etiket}</strong>{' '}
            <span className="saglik-zaman">{goreliZaman(b.last_success_at)}</span>{' '}
            {sorun
              ? <span className="rozet hata">{sessiz.length ? `${sessiz.length} sessiz` : 'son tur hatalı'}</span>
              : veriYok || bayat
                ? <span className="rozet uyari">{veriYok ? 'veri yok' : 'bayat'}</span>
                : <span className="rozet ok">ok</span>}
          </span>
        )
      })}
      {kuyruk && (
        // Bulgu 6 (2026-10-16): retranslate 3 gun takili kaldi, serit her bolumu "ok" gosterdi.
        // stalled: bekleyen var ve son 3 tur (~6 sa) hic kayit cevirmedi (news/fetch_runs.py).
        <span className="saglik-ogesi" title={`Bekleyen çeviri: ${kuyruk.pending}`}>
          <strong>Çeviri kuyruğu</strong>{' '}
          <span className="saglik-zaman">{goreliZaman(kuyruk.last_success_at)}</span>{' '}
          {kuyruk.stalled
            ? <span className="rozet hata">ilerlemiyor</span>
            : kuyruk.pending > 0
              ? <span className="rozet bilgi">{kuyruk.pending} bekliyor</span>
              : <span className="rozet ok">ok</span>}
        </span>
      )}
    </div>
  )
}
