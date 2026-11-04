// Okuma paneli metin yardimcilari. KEV regex'i news/kev.py ile ayni tutulur.
const KEV_ONEK = /^Added to the CISA KEV catalog on (\d{4}-\d{2}-\d{2})(?:; required action due (\d{4}-\d{2}-\d{2}))?\.\s*/
const TURKCE_HARF = /[çğıöşüÇĞİÖŞÜ]/
const ISARET_KELIMELER = new Set(['the', 'and', 'of', 'to', 'is', 'which', 'allows', 'attacker', 'vulnerability', 'could', 'with'])
const KISA_SINIR = 40

// Takvimde var olan YYYY-MM-DD ise ayni dizeyi, aksi halde null dondurur (Python _tarih esdegeri).
const gecerliTarih = (s) => {
  const d = new Date(`${s}T00:00:00Z`)
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s ? s : null
}

// GitHub Advisory/CIRCL aciklamalari Markdown gelir (2026-11-04: ~900 CVE "## Summary", "### Impact", kod
// bloklari, **kalin**, [baglanti](url)). Liste ve okuma paneli duz metin gosterir: isaretler atilir, basliklar
// kendi paragrafi olur, kod blogu satirlari korunur. Metnin ilk satiri kisa bir baslik ("## Summary",
// "## Özet") ise tamamen atilir; ozet satiri ilk paragraf olarak onun yerine gecer.
const MD_BASLIK = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/
const MD_CIT = /^\s{0,3}(```|~~~)/
const ILK_BASLIK_AZAMI_KELIME = 4

const satirIciSadelestir = (satir) => satir
  .replace(/\[([^\]\n]+)\]\((https?:\/\/[^)\s]+)\)/g, '$1')
  // Yalniz **kalin**: __kalin__ bicimi Python adlarini (__init__) bozar
  .replace(/\*\*(?=\S)([^*\n]+?)\*\*/g, '$1')
  .replace(/`([^`\n]+)`/g, '$1')

export const markdownSadelestir = (metin) => {
  const satirlar = (metin || '').split(/\r?\n/)
  const cikti = []
  let kodda = false
  let ilkSatir = true
  for (const satir of satirlar) {
    if (MD_CIT.test(satir)) {
      kodda = !kodda
      cikti.push('')
      continue
    }
    if (kodda) {
      cikti.push(satir)
      continue
    }
    const baslik = MD_BASLIK.exec(satir)
    if (baslik) {
      const yazi = satirIciSadelestir(baslik[1])
      const kisa = yazi.split(/\s+/).filter(Boolean).length <= ILK_BASLIK_AZAMI_KELIME
      if (!(ilkSatir && kisa) && yazi) cikti.push('', yazi, '')
    } else {
      cikti.push(satirIciSadelestir(satir))
    }
    if (satir.trim()) ilkSatir = false
  }
  return cikti.join('\n').replace(/\n{3,}/g, '\n\n').trim()
}

export const paragraflar = (metin) =>
  (metin || '').split(/\r?\n\s*\r?\n/).map(p => p.trim()).filter(Boolean)

export const kevOnekiAyir = (metin) => {
  const m = metin || ''
  const e = KEV_ONEK.exec(m)
  const kevEklenme = e ? gecerliTarih(e[1]) : null
  if (!kevEklenme) return { kevEklenme: null, sonTarih: null, govde: m }
  return { kevEklenme, sonTarih: e[2] ? gecerliTarih(e[2]) : null, govde: m.slice(e[0].length) }
}

// Kisa paragraflar (urun adi, surum) hic isaretlenmez; digerleri orijinalle ayniysa ya da Ingilizce gorunuyorsa isaretlenir.
export const cevrilmemisMi = (trParagraf, orijinalParagraflar) => {
  const p = (trParagraf || '').trim()
  if (p.length < KISA_SINIR) return false
  if ((orijinalParagraflar || []).some(o => o.trim() === p)) return true
  if (TURKCE_HARF.test(p)) return false
  const bulunan = new Set((p.toLowerCase().match(/\p{L}+/gu) || []).filter(k => ISARET_KELIMELER.has(k)))
  return bulunan.size >= 2
}

// Degisiklik gunlugu paragrafindaki "#123 · @yazar" PR etiketini baglanti icin ayirir (utils/okumaKaydi).
// Yazar etiketi izlemeyen "#12" gibi numaralar duz metin kalir.
const PR_ETIKETI = /#(\d+)(?= · @)/g

export const prParcalari = (metin) => {
  const m = metin || ''
  const parcalar = []
  let son = 0
  for (const e of m.matchAll(PR_ETIKETI)) {
    if (e.index > son) parcalar.push({ metin: m.slice(son, e.index) })
    parcalar.push({ pr: e[1] })
    son = e.index + e[0].length
  }
  if (son < m.length) parcalar.push({ metin: m.slice(son) })
  return parcalar
}

export const okumaIcerigi = ({ govdeTr, govdeOrijinal } = {}) => {
  const orijinal = paragraflar(govdeOrijinal)
  const tr = paragraflar(govdeTr)
  if (tr.length === 0) {
    return {
      paragraflar: orijinal.map(metin => ({ metin, cevrilmedi: false })),
      orijinal,
      tamamenCevrilmedi: orijinal.length > 0,
    }
  }
  return {
    paragraflar: tr.map(metin => ({ metin, cevrilmedi: cevrilmemisMi(metin, orijinal) })),
    orijinal,
    tamamenCevrilmedi: false,
  }
}
