// Liste altindaki numarali sayfa cubugu (spec 2026-11-05 G4): ilk, son ve gecerli sayfanin iki
// komsusu gorunur, aradakiler "…" olur; tek sayfada cubuk gizlenir. Gorunum filtre cubugundaki
// cubuk dugmeleriyle ayni, gecerli sayfa vurgu renginde (styles/tema.css .sayfa-cubugu).

const KOMSU = 2

// [1, '…', 4, 5, 6, 7, 8, '…', 20]; tek sayfalik bosluk "…" yerine o sayfayla doldurulur
const sayfaListesi = (sayfa, sayfaSayisi) => {
  const gorunen = new Set([1, sayfaSayisi])
  for (let s = sayfa - KOMSU; s <= sayfa + KOMSU; s++) {
    if (s >= 1 && s <= sayfaSayisi) gorunen.add(s)
  }
  const sirali = [...gorunen].sort((a, b) => a - b)
  const sonuc = []
  sirali.forEach((s, i) => {
    const onceki = sirali[i - 1]
    if (onceki !== undefined && s - onceki === 2) sonuc.push(onceki + 1)
    else if (onceki !== undefined && s - onceki > 2) sonuc.push('…')
    sonuc.push(s)
  })
  return sonuc
}

export default function SayfaCubugu({ sayfa, sayfaSayisi, onSayfa }) {
  if (!sayfaSayisi || sayfaSayisi <= 1) return null

  const git = (hedef) => {
    if (hedef !== sayfa && hedef >= 1 && hedef <= sayfaSayisi) onSayfa(hedef)
  }

  return (
    <nav className="sayfa-cubugu" aria-label="Sayfalar">
      <ul>
        <li>
          <button type="button" className="sayfa-dugmesi" disabled={sayfa <= 1} onClick={() => git(sayfa - 1)}>
            ‹ Önceki
          </button>
        </li>
        {sayfaListesi(sayfa, sayfaSayisi).map((s, i) => (
          s === '…'
            ? <li key={`bosluk-${i}`} className="sayfa-boslugu">…</li>
            : (
              <li key={s}>
                <button
                  type="button"
                  className={`sayfa-dugmesi${s === sayfa ? ' gecerli' : ''}`}
                  aria-current={s === sayfa ? 'page' : undefined}
                  onClick={() => git(s)}
                >
                  {s}
                </button>
              </li>
            )
        ))}
        <li>
          <button
            type="button"
            className="sayfa-dugmesi"
            disabled={sayfa >= sayfaSayisi}
            onClick={() => git(sayfa + 1)}
          >
            Sonraki ›
          </button>
        </li>
      </ul>
    </nav>
  )
}
