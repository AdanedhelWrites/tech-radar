import { Badge } from 'react-bootstrap'

// LibreTranslate cevirileri Google'dan belirgin sekilde dusuk kalitelidir ve
// anlam hatasi icerebilir (spec 2026-09-14, bolum 2.4). Okuyucu uyarilir; Google
// erisilebilir oldugunda bu kayitlar otomatik olarak yukseltilir.
const ACIKLAMA =
  'LibreTranslate ile çevrildi. Google erişilebilir olduğunda otomatik olarak iyileştirilecek; anlam hatası olabilir, orijinal metne bakın.'

export default function MakineCevirisiEtiketi({ kayit, className = 'ms-2' }) {
  if (kayit?.translation_provider !== 'libretranslate') return null
  return (
    <Badge bg="warning" text="dark" className={className} title={ACIKLAMA}>
      Makine çevirisi
    </Badge>
  )
}

export const makineCevirisiHtml = (kayit) =>
  kayit?.translation_provider === 'libretranslate'
    ? `<span class="badge" style="background:#ffc107;color:#212529" title="${ACIKLAMA}">Makine çevirisi</span>`
    : ''
