import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CvssGrafigi from './CvssGrafigi'

const noktalar = [
  { cve_id: 'CVE-2026-1', cvss_score: 9.8 },
  { cve_id: 'CVE-2026-2', cvss_score: 8.1 },
  { cve_id: 'CVE-2026-3', cvss_score: 5.0 },
]

describe('CvssGrafigi', () => {
  it('gercek bant sayilarini erisilebilir etikette ve lejantta gosterir', () => {
    render(<CvssGrafigi noktalar={noktalar} skorsuz={0} sayilar={{ kritik: 224, yuksek: 682, orta: 951 }} />)

    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label', 'CVSS dağılımı, son 7 gün: 224 kritik, 682 yüksek, 951 orta')
    expect(screen.getByText('Kritik 224')).toBeInTheDocument()
    expect(screen.getByText('Yüksek 682')).toBeInTheDocument()
    expect(screen.getByText('Orta 951')).toBeInTheDocument()
  })

  it('sayilar yoksa cizilen noktalari sayar', () => {
    render(<CvssGrafigi noktalar={noktalar} skorsuz={2} />)

    expect(screen.getByRole('img')).toHaveAttribute(
      'aria-label', 'CVSS dağılımı, son 7 gün: 1 kritik, 1 yüksek, 1 orta')
    expect(screen.getByText('2 skorsuz')).toBeInTheDocument()
  })
})
