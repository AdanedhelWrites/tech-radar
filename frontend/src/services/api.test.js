import { describe, it, expect } from 'vitest'
import api from './api'

describe('api', () => {
  it('istek_zaman_asimi_30_sn', () => {
    // Asili kalan istek 5 sn yenilemesini (useListeSorgusu bekleyen) sonsuza dek durdurmasin
    expect(api.defaults.timeout).toBe(30000)
  })
})
