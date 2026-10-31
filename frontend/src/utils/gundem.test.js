import { describe, it, expect } from 'vitest'
import { gundemBirlestir } from './gundem'

const kayit = (id, created_at) => ({ id, created_at })

describe('gundemBirlestir', () => {
  const listeler = [
    { bolum: 'Siber Güvenlik', kayitlar: [kayit(1, '2026-10-31T10:00:00Z'), kayit(2, '2026-10-31T07:00:00Z'), kayit(3, '2026-10-30T07:00:00Z')] },
    { bolum: 'Kubernetes', kayitlar: [kayit(4, '2026-10-31T09:00:00Z'), kayit(5, '2026-10-31T06:00:00Z'), kayit(6, '2026-10-29T07:00:00Z')] },
    { bolum: 'SRE', kayitlar: [kayit(7, '2026-10-31T11:00:00Z'), kayit(8, '2026-10-31T05:00:00Z'), kayit(9, '2026-10-28T07:00:00Z')] },
  ]

  it('created_at azalan ve adet sinirli', () => {
    const s = gundemBirlestir(listeler)
    expect(s).toHaveLength(6)
    expect(s.map(x => x.kayit.id)).toEqual([7, 1, 4, 2, 5, 8])
    expect(s[0]).toEqual({ bolum: 'SRE', kayit: kayit(7, '2026-10-31T11:00:00Z') })
  })
  it('adet verilebilir', () => expect(gundemBirlestir(listeler, 2).map(x => x.kayit.id)).toEqual([7, 1]))
  it('eksik ve bozuk created_at sona gider', () => {
    const s = gundemBirlestir([{ bolum: 'A', kayitlar: [kayit(1, null), kayit(2, 'bozuk'), kayit(3, '2026-10-31T00:00:00Z')] }])
    expect(s.map(x => x.kayit.id)).toEqual([3, 1, 2])
  })
  it('bos girdi bos liste olur', () => {
    expect(gundemBirlestir([])).toEqual([])
    expect(gundemBirlestir([{ bolum: 'A', kayitlar: [] }])).toEqual([])
  })
})
