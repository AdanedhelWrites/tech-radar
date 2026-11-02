// Bolum listelerini created_at azalan tek gundem listesinde birlestirir. Eksik/bozuk tarih sona gider.
const zaman = (iso) => {
  const t = Date.parse(iso)
  return Number.isNaN(t) ? -Infinity : t
}

export const gundemBirlestir = (listeler, adet = 6) =>
  listeler
    .flatMap(({ bolum, kayitlar }) => kayitlar.map(kayit => ({ bolum, kayit })))
    .sort((a, b) => zaman(b.kayit.created_at) - zaman(a.kayit.created_at))
    .slice(0, adet)
