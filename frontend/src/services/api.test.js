import { describe, it, expect } from 'vitest'
import api, { newsApi, cveApi, k8sApi, sreApi, devtoolsApi, aiApi } from './api'

describe('api', () => {
  it('istek_zaman_asimi_30_sn', () => {
    // Asili kalan istek 5 sn yenilemesini (useListeSorgusu bekleyen) sonsuza dek durdurmasin
    expect(api.defaults.timeout).toBe(30000)
  })

  it('bolum_apilerinde_disa_aktarim_ucu_yok', () => {
    // 2026-11-05: HTML rapor liste ucundan kurulur; /api/*/export/ uclari kaldirildi
    for (const bolum of [newsApi, cveApi, k8sApi, sreApi, devtoolsApi, aiApi]) {
      expect(Object.keys(bolum).filter((ad) => ad.startsWith('export'))).toEqual([])
    }
  })
})
