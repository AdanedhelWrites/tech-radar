import { skorSinifi } from '../../utils/cve'

// CVSS dagilim grafigi (spec 2026-10-31 G3, §6). Anlam yalniz merkeze uzaklikta: ic halka >= 9,
// orta 7-8.9, dis 4-6.9. Aci cve_id karmasindan deterministik: yenilemede noktalar yer degistirmez.
// Tarama animasyonu tema.css'te (.cvss-polar::after, 7 sn); hareket azaltma kuralinda durur.

const MERKEZ = 85 // .cvss-polar 170px; halka sinirlari 28 / 56 / 84 px
const SKOR_ADI = { kritik: 'kritik', yuksek: 'yüksek', orta: 'orta' }

// FNV-1a 32 bit
const karma = (metin) => {
  let h = 2166136261
  for (let i = 0; i < metin.length; i++) {
    h ^= metin.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

// Halka icinde skor yukseldikce merkeze yaklasir; halka sinirlarina 2 px pay birakilir
const yaricap = (skor) => {
  if (skor >= 9) return 6 + (10 - Math.min(skor, 10)) * 20 // 6..26
  if (skor >= 7) return 30 + (9 - skor) * 11 // 30..52
  return 58 + (7 - skor) * (22 / 3) // 58..80
}

const noktaKonumu = (cveId, skor) => {
  const aci = ((karma(String(cveId)) % 360) * Math.PI) / 180
  const r = yaricap(skor)
  return { x: MERKEZ + r * Math.cos(aci), y: MERKEZ + r * Math.sin(aci) }
}

export default function CvssGrafigi({ noktalar, skorsuz }) {
  const cizilen = noktalar
    .filter(n => Number.isFinite(n?.cvss_score) && skorSinifi(n.cvss_score))
    .map(n => ({ ...n, sinif: skorSinifi(n.cvss_score), ...noktaKonumu(n.cve_id, n.cvss_score) }))
  const say = (sinif) => cizilen.filter(n => n.sinif === sinif).length
  const ozet = `CVSS dağılımı, son 7 gün: ${say('kritik')} kritik, ${say('yuksek')} yüksek, ${say('orta')} orta`

  return (
    <div className="cam-kart cvss-grafigi">
      <div className="etiket-kucuk text-center">CVSS Dağılımı</div>
      <div className="cvss-polar" role="img" aria-label={ozet}>
        {cizilen.map(n => (
          <span
            key={n.cve_id}
            className={`cvss-nokta ${n.sinif}`}
            style={{ left: `${n.x}px`, top: `${n.y}px` }}
            title={`${n.cve_id} · CVSS ${n.cvss_score.toFixed(1)} (${SKOR_ADI[n.sinif]})`}
          />
        ))}
      </div>
      <div className="cvss-lejant">
        <span><i className="kritik" aria-hidden="true" />Kritik</span>
        <span><i className="yuksek" aria-hidden="true" />Yüksek</span>
        <span><i className="orta" aria-hidden="true" />Orta</span>
        {skorsuz > 0 && <span className="skorsuz">{`${skorsuz} skorsuz`}</span>}
      </div>
    </div>
  )
}
