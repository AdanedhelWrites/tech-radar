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
