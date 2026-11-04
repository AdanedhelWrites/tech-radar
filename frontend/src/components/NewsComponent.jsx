import {
  FaSkullCrossbones, FaLaptopCode, FaShieldAlt, FaMoon, FaUserSecret,
  FaGlobeAmericas, FaBullhorn, FaLifeRing, FaBookOpen, FaBroadcastTower,
  FaTerminal, FaUserShield
} from 'react-icons/fa'
import { newsApi } from '../services/api'
import HaberBolumu from './bolum/HaberBolumu'

// Siber Guvenlik sayfasi (spec 2026-10-31 G4, 2026-11-05 G1): gorunum bolum/BolumSayfasi'nda,
// veri, filtre, sayfalama ve eylemler bolum/HaberBolumu'nda; burada yalniz bolume ozgu tanim.

const TANIM = {
  bolum: 'news',
  baslik: 'Siber Güvenlik',
  kimlik: 'news',
  kaynaklar: [
    { id: 'source1', name: 'The Hacker News', value: 'The Hacker News', icon: FaSkullCrossbones },
    { id: 'source2', name: 'Bleeping Computer', value: 'Bleeping Computer', icon: FaLaptopCode },
    { id: 'source3', name: 'SecurityWeek', value: 'SecurityWeek', icon: FaShieldAlt },
    { id: 'source4', name: 'Dark Reading', value: 'Dark Reading', icon: FaMoon },
    { id: 'source5', name: 'Krebs on Security', value: 'Krebs on Security', icon: FaUserSecret },
    { id: 'source6', name: 'The Record', value: 'The Record', icon: FaGlobeAmericas },
    { id: 'source7', name: 'CyberScoop', value: 'CyberScoop', icon: FaBullhorn },
    { id: 'source8', name: 'Help Net Security', value: 'Help Net Security', icon: FaLifeRing },
    { id: 'source9', name: 'Infosecurity Magazine', value: 'Infosecurity Magazine', icon: FaBookOpen },
    { id: 'source10', name: 'SANS ISC', value: 'SANS ISC', icon: FaBroadcastTower },
    { id: 'source11', name: 'The Register', value: 'The Register', icon: FaTerminal },
    { id: 'source12', name: 'Security Affairs', value: 'Security Affairs', icon: FaUserShield },
  ],
  api: {
    liste: (params) => newsApi.getNews(params),
    cek: (veri) => newsApi.fetchNews(veri),
    temizle: () => newsApi.clearCache(),
    istatistik: () => newsApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'Siber güvenlik haberleri yüklenirken hata oluştu',
    cekimHatasi: 'Siber güvenlik haberleri getirilirken hata oluştu',
    temizleOnayi: 'Tüm haberler silinecek ve sıfırlanacak. Emin misiniz?',
  },
  rapor: {
    belgeBasligi: 'Siber Güvenlik Raporu',
    baslik: 'Siber Güvenlik Haberleri Raporu',
    birim: 'haber',
    dosyaOnEki: 'siber_guvenlik_raporu',
    // Haberde tarih date alaninda, govde ozetle tamamlanir
    tarih: (k) => k.date || k.original_date || '',
    icerik: (k) => k.turkish_description || k.turkish_summary || '',
  },
}

export default function NewsComponent() {
  return <HaberBolumu tanim={TANIM} />
}
