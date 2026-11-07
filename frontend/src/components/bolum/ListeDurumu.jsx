// Liste yerine gosterilecek durum (alti bolum: BolumSayfasi ve Zafiyetler). null: liste cizilir.
// 2026-11-07 inceleme: yeni sorgu hatayla bitince eski filtrenin listesi ekranda kaliyordu; ilk yukleme
// hatasi da "Liste bos" yazip hatayi bos veritabani gibi gosteriyordu. Eldeki yanit gecerli sorguya ait
// degilse (guncel false) ve hata varsa liste yerine "Yeniden dene" kutusu cizilir. Sessiz yenilemenin
// hatasi useListeSorgusu'nda hata olarak yazilmaz: ekrandaki guncel liste kalir.
export default function listeDurumu({
  yukleniyor, hata, guncel, adet, yukleniyorMetni, bosMetni, onYeniden,
}) {
  if (yukleniyor) return <p className="liste-bos">{yukleniyorMetni}</p>
  if (hata && !guncel) {
    return (
      <div className="liste-bos liste-hata" role="alert">
        <p>Kayıtlar yüklenemedi. Bağlantıyı ya da sunucuyu kontrol edip yeniden deneyin.</p>
        <button type="button" className="cubuk-dugme" onClick={onYeniden}>Yeniden dene</button>
      </div>
    )
  }
  if (adet === 0) return <p className="liste-bos">{bosMetni}</p>
  return null
}
