import { useCallback, useEffect, useState } from 'react'
import { Badge } from 'react-bootstrap'
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

export default function SaglikSeridi() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState(false)

  const yukle = useCallback(async () => {
    try {
      const yanit = await saglikApi.getSaglik()
      setVeri(yanit.data.sections)
      setHata(false)
    } catch {
      setHata(true)
    }
  }, [])

  useEffect(() => { yukle() }, [yukle])
  useAraliklaYenile(yukle, YENILEME_MS)

  if (hata) return <div className="text-muted small mb-4">Sağlık bilgisi alınamadı.</div>
  if (!veri) return null

  return (
    <div className="d-flex flex-wrap justify-content-center gap-2 mb-4" data-testid="saglik-seridi">
      {Object.entries(BOLUM_ETIKETLERI).map(([ad, etiket]) => {
        const b = veri[ad] || {}
        const sessiz = b.silent_sources || []
        const sorun = sessiz.length > 0 || b.last_status === 'failure'
        const baslik = sessiz.length ? `Sessiz: ${sessiz.join(', ')}` : 'Tüm kaynaklar veri döndürüyor'
        return (
          <span key={ad} className="border rounded px-2 py-1 small" title={baslik}>
            <strong>{etiket}</strong>{' '}
            <span className="text-muted">{goreliZaman(b.last_success_at)}</span>{' '}
            {sorun
              ? <Badge bg="danger">{sessiz.length ? `${sessiz.length} sessiz` : 'son tur hatalı'}</Badge>
              : <Badge bg="success">ok</Badge>}
          </span>
        )
      })}
    </div>
  )
}
