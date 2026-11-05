import { FaDharmachakra, FaGithub, FaCloud } from 'react-icons/fa'
import { k8sApi } from '../services/api'
import { KATEGORI } from '../utils/okumaKaydi'
import HaberBolumu from './bolum/HaberBolumu'

// Kubernetes sayfasi (spec 2026-10-31 G4, 2026-11-05 G1): gorunum bolum/BolumSayfasi'nda,
// veri, filtre, sayfalama ve eylemler bolum/HaberBolumu'nda; burada bolume ozgu tanim ve
// kategori filtresi (adreste ?kategori=<category>, sunucuda suzulur). Kategori etiketleri
// utils/okumaKaydi'daki tek kaynaktan gelir. GitHub Releases'in yapisal degisiklik gunlugu okuma
// panelinde okunur paragraflara cevrilir (utils/okumaKaydi degisiklikGunlugu).

// '' = Tumu (adrese yazilmaz)
const KATEGORI_SECENEKLERI = [['', 'Tümü'], ...Object.entries(KATEGORI)]

function KategoriFiltresi({ sorgu, degistir }) {
  return (
    <div className="filtre-grubu siddet-secici" role="group" aria-label="Kategori filtresi">
      {KATEGORI_SECENEKLERI.map(([deger, etiket]) => (
        <button
          key={deger || 'tumu'}
          type="button"
          className={`siddet-dugmesi${sorgu.kategori === deger ? ' secili' : ''}`}
          aria-pressed={sorgu.kategori === deger}
          onClick={() => degistir({ kategori: deger })}
        >
          {etiket}
        </button>
      ))}
    </div>
  )
}

const TANIM = {
  bolum: 'kubernetes',
  baslik: 'Kubernetes',
  kimlik: 'k8s',
  kaynaklar: [
    { id: 'k8s_source1', name: 'K8s Blog', value: 'K8s Blog', icon: FaDharmachakra },
    { id: 'k8s_source2', name: 'GitHub Releases', value: 'GitHub Releases', icon: FaGithub },
    { id: 'k8s_source3', name: 'CNCF Blog', value: 'CNCF Blog', icon: FaCloud },
  ],
  api: {
    liste: (params) => k8sApi.getK8s(params),
    cek: (veri) => k8sApi.fetchK8s(veri),
    temizle: () => k8sApi.clearCache(),
    istatistik: () => k8sApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'Kubernetes haberleri yüklenirken hata oluştu',
    cekimHatasi: 'Kubernetes haberleri getirilirken hata oluştu',
    temizleOnayi: 'Tüm Kubernetes haberleri silinecek ve sıfırlanacak. Emin misiniz?',
  },
  rapor: {
    belgeBasligi: 'Kubernetes Raporu',
    baslik: 'Kubernetes Haberleri Raporu',
    birim: 'haber',
    dosyaOnEki: 'kubernetes_raporu',
    vurgu: '#326ce5',
    // Degisiklik gunlugunun girintisi raporda korunur
    boslukKorunur: true,
  },
  ekAnahtarlar: ['kategori'],
  // Gecersiz ?kategori= istege gitmez (Tumu sayilir)
  ekDegerler: { kategori: Object.keys(KATEGORI) },
  ekFiltre: (ozellikler) => <KategoriFiltresi {...ozellikler} />,
  dagilim: (istatistik) => Object.entries(istatistik.by_category || {})
    .map(([kategori, adet]) => [KATEGORI[kategori] || kategori, adet]),
}

export default function KubernetesComponent() {
  return <HaberBolumu tanim={TANIM} />
}
