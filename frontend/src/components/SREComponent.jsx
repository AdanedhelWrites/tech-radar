import { FaCalendarWeek, FaInfoCircle, FaBell, FaGoogle, FaCode } from 'react-icons/fa'
import { sreApi } from '../services/api'
import HaberBolumu from './bolum/HaberBolumu'

// SRE sayfasi (spec 2026-10-31 G4, 2026-11-05 G1): gorunum bolum/BolumSayfasi'nda,
// veri, filtre, sayfalama ve eylemler bolum/HaberBolumu'nda; burada yalniz bolume ozgu tanim.

const TANIM = {
  bolum: 'sre',
  baslik: 'SRE',
  kimlik: 'sre',
  kaynaklar: [
    { id: 'sre_source1', name: 'SRE Weekly', value: 'SRE Weekly', icon: FaCalendarWeek },
    { id: 'sre_source2', name: 'InfoQ SRE', value: 'InfoQ SRE', icon: FaInfoCircle },
    { id: 'sre_source3', name: 'PagerDuty Eng', value: 'PagerDuty Eng', icon: FaBell },
    { id: 'sre_source4', name: 'Google Cloud SRE', value: 'Google Cloud SRE', icon: FaGoogle },
    { id: 'sre_source5', name: 'DZone DevOps', value: 'DZone DevOps', icon: FaCode },
  ],
  api: {
    liste: (params) => sreApi.getSRE(params),
    cek: (veri) => sreApi.fetchSRE(veri),
    temizle: () => sreApi.clearCache(),
    istatistik: () => sreApi.getStats(),
  },
  metinler: {
    yuklemeHatasi: 'SRE haberleri yüklenirken hata oluştu',
    cekimHatasi: 'SRE haberleri getirilirken hata oluştu',
    temizleOnayi: 'Tüm SRE haberleri silinecek ve sıfırlanacak. Emin misiniz?',
  },
  rapor: {
    belgeBasligi: 'SRE Raporu',
    baslik: 'SRE Haberleri Raporu',
    birim: 'haber',
    dosyaOnEki: 'sre_raporu',
  },
}

export default function SREComponent() {
  return <HaberBolumu tanim={TANIM} />
}
