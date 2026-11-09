import { FaRobot, FaMicrochip, FaNewspaper, FaEnvelope } from 'react-icons/fa'
import { aiApi } from '../services/api'
import HaberBolumu from './bolum/HaberBolumu'

// Yapay Zeka sayfasi (spec 2026-10-31 G4, 2026-11-05 G1): gorunum bolum/BolumSayfasi'nda,
// veri, filtre, sayfalama ve eylemler bolum/HaberBolumu'nda; burada yalniz bolume ozgu tanim.

const TANIM = {
  bolum: 'ai',
  baslik: 'Yapay Zeka',
  kimlik: 'ai',
  kaynaklar: [
    { id: 'ai_source1', name: 'Hugging Face', value: 'Hugging Face', icon: FaRobot },
    { id: 'ai_source2', name: 'MIT Tech Review AI', value: 'MIT Tech Review AI', icon: FaMicrochip },
    { id: 'ai_source3', name: 'MarkTechPost', value: 'MarkTechPost', icon: FaMicrochip },
    { id: 'ai_source4', name: 'AWS ML Blog', value: 'AWS ML Blog', icon: FaRobot },
    { id: 'ai_source5', name: 'TechCrunch AI', value: 'TechCrunch AI', icon: FaMicrochip },
    { id: 'ai_source6', name: 'Google DeepMind', value: 'Google DeepMind', icon: FaRobot },
    { id: 'ai_source8', name: 'OpenAI Blog', value: 'OpenAI Blog', icon: FaRobot },
    // 2026-10-14: KDnuggets (403) yerine; value arka uctaki kaynak adiyla birebir (news/ai_scraper.py)
    { id: 'ai_source9', name: 'Ars Technica AI', value: 'Ars Technica AI', icon: FaNewspaper },
    { id: 'ai_source10', name: 'Import AI', value: 'Import AI', icon: FaEnvelope },
  ],
  api: {
    liste: (params) => aiApi.getAINews(params),
    cek: (veri) => aiApi.fetchAINews(veri),
    temizle: () => aiApi.clearCache(),
    istatistik: () => aiApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'Yapay Zeka güncellemeleri yüklenirken hata oluştu',
    cekimHatasi: 'Yapay Zeka güncellemeleri getirilirken hata oluştu',
    temizleOnayi: 'Tüm Yapay Zeka güncellemeleri silinecek ve sıfırlanacak. Emin misiniz?',
  },
  rapor: {
    belgeBasligi: 'Yapay Zeka Raporu',
    baslik: 'Yapay Zeka Güncellemeleri Raporu',
    birim: 'güncelleme',
    dosyaOnEki: 'ai_haberleri_raporu',
    vurgu: '#8e44ad',
  },
}

export default function AINewsComponent() {
  return <HaberBolumu tanim={TANIM} />
}
