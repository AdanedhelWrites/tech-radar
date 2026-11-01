import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from './App'

// Sayfa bilesenleri API cagirir; gezinme testinde bos bilesenlere cevrilir
vi.mock('./components/NewsComponent', () => ({ default: () => null }))
vi.mock('./components/CVEComponent', () => ({ default: () => null }))
vi.mock('./components/KubernetesComponent', () => ({ default: () => null }))
vi.mock('./components/SREComponent', () => ({ default: () => null }))
vi.mock('./components/DevToolsComponent', () => ({ default: () => null }))
vi.mock('./components/AINewsComponent', () => ({ default: () => null }))
vi.mock('./components/genel/GenelBakis', () => ({ default: () => null }))

const MENU = [
  ['Genel Bakış', '/'],
  ['Zafiyetler', '/cve'],
  ['Siber Güvenlik', '/news'],
  ['Kubernetes', '/k8s'],
  ['SRE', '/sre'],
  ['DevTools', '/devtools'],
  ['Yapay Zeka', '/ai'],
]

const uygulama = (yol = '/') => render(
  <MemoryRouter initialEntries={[yol]}>
    <App />
  </MemoryRouter>,
)

describe('App gezinme', () => {
  it('yedi menu baglantisini sirasiyla ve dogru rotalarla gosterir', () => {
    uygulama()
    const menu = screen.getByRole('navigation', { name: 'Ana menü' })
    const baglantilar = within(menu).getAllByRole('link')
    expect(baglantilar.map((a) => [a.textContent.trim(), a.getAttribute('href')])).toEqual(MENU)
  })

  it('ust bantta logo adi ve alt baslik vardir', () => {
    uygulama()
    expect(screen.getByText('Teknoloji Radar', { selector: '.marka-adi' })).toBeInTheDocument()
    expect(screen.getByText('Tehdit ve Teknoloji İzleme')).toBeInTheDocument()
  })

  it('tema dugmesi yoktur', () => {
    uygulama()
    expect(screen.queryByLabelText(/Karanlık Mod|Aydınlık Mod/)).toBeNull()
  })

  it('aktif rota baglantisi isaretlenir', () => {
    uygulama('/cve')
    expect(screen.getByRole('link', { name: 'Zafiyetler' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Genel Bakış' })).not.toHaveAttribute('aria-current')
  })
})
