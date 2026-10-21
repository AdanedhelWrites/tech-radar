import { Badge } from 'react-bootstrap'

// Her kayit hangi saglayiciyla cevrildigini gosterir (spec 2026-09-15, bolum 3.5).
// LibreTranslate dusuk kalitelidir ve anlam hatasi icerebilir: sari uyari.
// Gemini ve Google (eski kayitlar) notr gri bilgi rozeti. Bos/null: rozet yok.
const ROZETLER = {
  libretranslate: {
    metin: 'Makine çevirisi: LibreTranslate',
    bg: 'warning', text: 'dark', arka: '#ffc107', on: '#212529',
    aciklama: 'Yerel LibreTranslate ile çevrildi; anlam hatası olabilir, orijinal metne bakın. En geç 2 saat içinde Gemini ile iyileştirilir.',
  },
  gemini: {
    metin: 'Çeviri: Gemini',
    bg: 'secondary', text: 'light', arka: '#6c757d', on: '#ffffff',
    aciklama: 'Gemini (gemini-3.5-flash-lite) ile çevrildi.',
  },
  google: {
    metin: 'Çeviri: Google',
    bg: 'secondary', text: 'light', arka: '#6c757d', on: '#ffffff',
    aciklama: 'Google Translate ile çevrildi.',
  },
}

// Hic cevrilememis kayit (fetch aninda LibreTranslate basarisiz, retranslate 5 denemede vazgecti ya da
// GEMINI_MAX_CHARS ustu): metin Ingilizce gosterilir; okuyucu bunu bilmeli (2026-10-14).
// 2026-10-21 (bulgu 6): onceden yalniz en az bir deneme yapilmis kayit isaretleniyordu; kuyruk takilinca
// hic denenmemis kayitlar (10-16'da 42, 10-21'de 16 Ingilizce baslik) rozetsiz kaliyordu. Saglayicisi
// bos ve ceviri bekleyen kaydin metni her durumda orijinaldir.
const CEVRILMEDI = {
  metin: 'Çevrilmedi: orijinal metin',
  bg: 'light', text: 'dark', arka: '#e9ecef', on: '#212529',
  aciklama: 'Çeviri sağlayıcıları bu kaydı çeviremedi (çok uzun ya da çevrilemeyen içerik); metin İngilizce gösteriliyor.',
}

const rozetSec = (kayit) =>
  ROZETLER[kayit?.translation_provider]
  || (kayit?.needs_translation && !kayit?.translation_provider ? CEVRILMEDI : null)

export default function CeviriEtiketi({ kayit, className = 'ms-2' }) {
  const rozet = rozetSec(kayit)
  if (!rozet) return null
  return (
    <Badge bg={rozet.bg} text={rozet.text} className={className} title={rozet.aciklama}>
      {rozet.metin}
    </Badge>
  )
}

export const ceviriEtiketiHtml = (kayit) => {
  const rozet = rozetSec(kayit)
  return rozet
    ? `<span class="badge" style="background:${rozet.arka};color:${rozet.on}" title="${rozet.aciklama}">${rozet.metin}</span>`
    : ''
}
