import { FaDatabase, FaStream, FaHdd, FaLeaf, FaEnvelope, FaSearch, FaBolt, FaGraduationCap,
  FaRobot, FaProjectDiagram, FaChartLine, FaGitlab, FaKey } from 'react-icons/fa'
import { devtoolsApi } from '../services/api'
import { KAYIT_TURU } from '../utils/okumaKaydi'
import HaberBolumu from './bolum/HaberBolumu'

// DevTools sayfasi (spec 2026-10-31 G4, 2026-11-05 G1): gorunum bolum/BolumSayfasi'nda,
// veri, filtre, sayfalama ve eylemler bolum/HaberBolumu'nda; burada yalniz bolume ozgu tanim.
// Surum ve kayit turu (release/blog/news) satirda ve panelde bilgi rozeti; tur dagilimi baslikta.
// Tur filtresi bugun yok, eklenmedi (plan 2026-11-05 Global Constraints).

const TANIM = {
  bolum: 'devtools',
  baslik: 'DevTools',
  kimlik: 'devtools',
  kaynaklar: [
    // 2026-10-14: MinIO cikarildi (ust kaynak Ekim 2025'ten beri surum yayinlamiyor)
    { id: 'dt_source2', name: 'Seq', value: 'Seq', icon: FaStream },
    { id: 'dt_source3', name: 'Ceph', value: 'Ceph', icon: FaHdd },
    { id: 'dt_source4', name: 'MongoDB', value: 'MongoDB', icon: FaLeaf },
    { id: 'dt_source5', name: 'PostgreSQL', value: 'PostgreSQL', icon: FaDatabase },
    { id: 'dt_source6', name: 'RabbitMQ', value: 'RabbitMQ', icon: FaEnvelope },
    { id: 'dt_source7', name: 'Elastic', value: 'Elastic', icon: FaSearch },
    { id: 'dt_source8', name: 'Redis', value: 'Redis', icon: FaBolt },
    { id: 'dt_source9', name: 'Moodle', value: 'Moodle', icon: FaGraduationCap },
    { id: 'dt_source10', name: 'LiteLLM', value: 'LiteLLM', icon: FaRobot },
    { id: 'dt_source11', name: 'LangGraph', value: 'LangGraph', icon: FaProjectDiagram },
    { id: 'dt_source12', name: 'Langfuse', value: 'Langfuse', icon: FaChartLine },
    { id: 'dt_source13', name: 'GitLab', value: 'GitLab', icon: FaGitlab },
    { id: 'dt_source14', name: 'Keycloak', value: 'Keycloak', icon: FaKey },
  ],
  api: {
    liste: (params) => devtoolsApi.getDevTools(params),
    cek: (veri) => devtoolsApi.fetchDevTools(veri),
    temizle: () => devtoolsApi.clearCache(),
    istatistik: () => devtoolsApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'DevTools güncellemeleri yüklenirken hata oluştu',
    cekimHatasi: 'DevTools güncellemeleri getirilirken hata oluştu',
    temizleOnayi: 'Tüm DevTools güncellemeleri silinecek ve sıfırlanacak. Emin misiniz?',
  },
  rapor: {
    belgeBasligi: 'DevTools Raporu',
    baslik: 'DevTools Güncellemeleri Raporu',
    birim: 'güncelleme',
    dosyaOnEki: 'devtools_raporu',
  },
  dagilim: (istatistik) => Object.entries(istatistik.by_type || {})
    .map(([tur, adet]) => [KAYIT_TURU[tur] || tur, adet]),
}

export default function DevToolsComponent() {
  return <HaberBolumu tanim={TANIM} />
}
