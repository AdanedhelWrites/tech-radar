import { GUN_SECENEKLERI } from '../../hooks/useListeSorgusu'

// Bolum filtre cubugunun ortak secenekleri (spec 2026-11-05 G4). Bilesen dosyasinin disinda:
// react-refresh bilesen dosyasindan bilesen olmayan disa aktarimi istemiyor.

// Donem: Son 1/3/7/14/30 gun ve Tumu (null)
export const DONEM_SECENEKLERI = [...GUN_SECENEKLERI, null]

export const donemEtiketi = (gun) => (gun === null ? 'Tümü' : `Son ${gun} gün`)

// Tarih siralamasi butun bolumlerde; Zafiyetler ayrica CVSS_SIRALAMASI'ni ekler
export const SIRALA_SECENEKLERI = [
  { deger: 'yeni', etiket: 'En yeni' },
  { deger: 'eski', etiket: 'En eski' },
]
export const CVSS_SIRALAMASI = { deger: 'cvss', etiket: 'En yüksek CVSS' }

// Cek kaynaklardan en fazla 15 gun ceker (kaynak tarafinin siniri); Tumu de 15
export const EN_FAZLA_CEKIM_GUNU = 15
export const cekimGunu = (gun) => (gun ? Math.min(gun, EN_FAZLA_CEKIM_GUNU) : EN_FAZLA_CEKIM_GUNU)

const sayi = (n) => Number(n || 0).toLocaleString('tr-TR')

// Sayim satiri: "Son 7 günde 1.234 kayıt · 26–50 gösteriliyor"; Tumu (gun null) donemsiz.
// adet: bu sayfadaki kayit sayisi.
export const sayimMetni = ({ gun, toplam, sayfa, boyut, adet }) => {
  const ilk = (sayfa - 1) * boyut + 1
  const aralik = `${sayi(ilk)}–${sayi(ilk + adet - 1)} gösteriliyor`
  return gun ? `Son ${gun} günde ${sayi(toplam)} kayıt · ${aralik}` : `${sayi(toplam)} kayıt · ${aralik}`
}
