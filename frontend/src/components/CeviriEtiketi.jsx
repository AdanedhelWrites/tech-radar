import { Badge } from 'react-bootstrap'

// Her kayit hangi saglayiciyla cevrildigini gosterir (spec 2026-09-15, bolum 3.5).
// LibreTranslate dusuk kalitelidir ve anlam hatasi icerebilir: sari uyari.
// Gemini, OpenRouter, DeepL ve Google (eski kayitlar) notr gri bilgi rozeti. Bos/null: rozet yok.
const ROZETLER = {
  libretranslate: {
    metin: 'Makine çevirisi: LibreTranslate',
    bg: 'warning', text: 'dark',
    aciklama: 'Yerel LibreTranslate ile çevrildi; anlam hatası olabilir, orijinal metne bakın. Haberler ile kritik ve yüksek zafiyetler gün içinde Gemini ile iyileştirilir.',
  },
  gemini: {
    metin: 'Çeviri: Gemini',
    bg: 'secondary', text: 'light',
    aciklama: 'Gemini (gemini-3.5-flash-lite) ile çevrildi.',
  },
  // Yedek zincir (spec 2026-11-02 G6, PR-C): birincil Gemini kullanilamazken
  openrouter: {
    metin: 'Çeviri: OpenRouter',
    bg: 'secondary', text: 'light',
    aciklama: 'OpenRouter ücretsiz modeliyle çevrildi.',
  },
  deepl: {
    metin: 'Çeviri: DeepL',
    bg: 'secondary', text: 'light',
    aciklama: 'DeepL API Free ile çevrildi.',
  },
  google: {
    metin: 'Çeviri: Google',
    bg: 'secondary', text: 'light',
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
  bg: 'light', text: 'dark',
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

// HTML rapor rozeti (utils/rapor ekRozetler): ham metin ve sinif, kacis rapor sablonunda.
// Sinif: notr 'ceviri'; LibreTranslate 'ceviri uyari'; cevrilmemis 'ceviri cevrilmedi'.
const RAPOR_SINIFI = { libretranslate: 'ceviri uyari' }

export const ceviriRozeti = (kayit) => {
  const rozet = rozetSec(kayit)
  if (!rozet) return null
  const sinif = rozet === CEVRILMEDI ? 'ceviri cevrilmedi' : (RAPOR_SINIFI[kayit.translation_provider] || 'ceviri')
  return { metin: rozet.metin, sinif }
}
