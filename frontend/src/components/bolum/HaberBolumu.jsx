import useBolumVerisi from '../../hooks/useBolumVerisi'
import BolumSayfasi, { BolumCubugu, HataUyarisi } from './BolumSayfasi'

// Bes haber bolumunun (Siber Guvenlik, Kubernetes, SRE, DevTools, Yapay Zeka) ortak bileseni
// (spec 2026-11-05 G1): veri ve eylemler hooks/useBolumVerisi'nde (Zafiyetler de ayni hook'u kullanir),
// gorunum bolum/BolumSayfasi'nda. Bolum bilesenleri yalniz bolume ozgu tanimi (tanim) verir:
//   bolum, baslik, kimlik + useBolumVerisi tanimi (kaynaklar, api, metinler, rapor, ekAnahtarlar)
//   istege bagli: dagilim(istatistik) -> [[etiket, adet]],
//                 ekFiltre({ sorgu, degistir }) -> filtre cubuguna eklenen oge

export default function HaberBolumu({ tanim }) {
  const { bolum, baslik, kimlik, dagilim = null, ekFiltre = null } = tanim
  const veri = useBolumVerisi(tanim)
  const { liste, istatistik } = veri

  return (
    <>
      <BolumSayfasi
        bolum={bolum}
        baslik={baslik}
        kayitlar={liste.kayitlar}
        yukleniyor={liste.yukleniyor}
        istatistik={istatistik}
        dagilim={dagilim ? dagilim(istatistik) : []}
        toplam={liste.toplam}
        sayfa={liste.sayfa}
        sayfaSayisi={liste.sayfaSayisi}
        boyut={liste.boyut}
        gun={liste.sorgu.gun}
        guncel={liste.guncel}
        hata={liste.hata}
        onYeniden={liste.yenile}
        tekilGetir={veri.tekilGetir}
        aramaVar={liste.sorgu.ara.length > 0}
        onSayfa={liste.sayfayaGit}
        cubuk={({ kapat }) => (
          <BolumCubugu
            kimlik={kimlik}
            {...veri.cubukOzellikleri(kapat)}
            ekFiltre={ekFiltre ? ekFiltre({ sorgu: liste.sorgu, degistir: liste.degistir }) : null}
          />
        )}
      />

      <HataUyarisi metin={veri.hata} onKapat={veri.hatayiKapat} />
    </>
  )
}
