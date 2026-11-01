// Zafiyet durumu basligi, alt cumle ve dort ozet kutusu (spec 2026-10-31 G3, pencereler §6).
// Kritik yoksa baslik sakin bir cumleye doner; bos durum da rahatlatici olmali.

const sayi = (deger) => (Number.isFinite(deger) ? deger : 0)

const altCumle = (ozet, kritik) => {
  const cumleler = []
  if (kritik > 0) {
    const kev = sayi(ozet.kev_count)
    if (kev > 0) cumleler.push(`Son 7 günde ${kev} zafiyet CISA KEV kataloğuna eklendi; aktif istismar doğrulanmış.`)
  } else {
    cumleler.push(`Son 7 günde ${sayi(ozet.high_count)} yüksek önem dereceli zafiyet kaydedildi.`)
  }
  // Yalniz gecerli bir son ziyaret gonderildiyse sunucu bu alani doner (ilk ziyarette yok).
  // Sayim yalniz CVE'leri kapsar (karar R10); 0 ise cumle gosterilmez.
  if (Number.isFinite(ozet.new_since_count) && ozet.new_since_count > 0) {
    cumleler.push(`Son ziyaretinizden bu yana ${ozet.new_since_count} yeni zafiyet kaydı eklendi.`)
  }
  return cumleler.join(' ')
}

function OzetKutusu({ deger, etiket, ton = '', not = null }) {
  return (
    <div className={`ozet-kutusu ${ton}`.trim()}>
      <b>{deger}</b>
      <span>{etiket}</span>
      {not && <em>{not}</em>}
    </div>
  )
}

function OzetIcerigi({ ozet }) {
  const kritik = sayi(ozet.critical_count)
  const yuksek = sayi(ozet.high_count)
  const kev = sayi(ozet.kev_count)
  const toplam = sayi(ozet.sources?.total)
  const sessiz = sayi(ozet.sources?.silent)
  const cumle = altCumle(ozet, kritik)

  return (
    <>
      {kritik > 0 ? (
        <h1 className="durum-baslik"><b>{`${kritik} kritik zafiyet`}</b> değerlendirme bekliyor</h1>
      ) : (
        <h1 className="durum-baslik sakin">Son 24 saatte kritik zafiyet yok</h1>
      )}
      {cumle && <p className="durum-cumle">{cumle}</p>}
      <div className="ozet-kutulari">
        <OzetKutusu deger={kritik} etiket="Kritik (CVSS ≥ 9.0)" ton={kritik > 0 ? 'kritik' : 'saglikli'} />
        <OzetKutusu deger={yuksek} etiket="Yüksek, son 7 gün" ton={yuksek > 0 ? 'yuksek' : ''} />
        <OzetKutusu deger={kev} etiket="Aktif istismar (KEV)" />
        <OzetKutusu
          deger={`${toplam - sessiz}/${toplam}`}
          etiket="Kaynak erişilebilir"
          ton={sessiz > 0 ? 'uyari' : 'saglikli'}
          not={sessiz > 0 ? `${sessiz} kaynak sessiz` : null}
        />
      </div>
    </>
  )
}

export default function DurumOzeti({ ozet, hata }) {
  return (
    <div className="durum-ozeti">
      <div className="etiket-kucuk">Zafiyet Durumu · Son 24 Saat</div>
      {hata ? (
        <p className="durum-hata">Özet bilgisi alınamadı.</p>
      ) : ozet ? (
        <OzetIcerigi ozet={ozet} />
      ) : (
        <p className="genel-bos">Özet yükleniyor…</p>
      )}
    </div>
  )
}
