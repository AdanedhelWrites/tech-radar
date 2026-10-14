import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import SaglikSeridi from './SaglikSeridi'
import { saglikApi } from '../services/api'

vi.mock('../services/api', () => ({ saglikApi: { getSaglik: vi.fn() } }))

const bolum = (ek = {}) => ({
  last_success_at: new Date(Date.now() - 3600 * 1000).toISOString(),
  last_status: 'success', pending_translation: 0, translation_given_up: 0, silent_sources: [], ...ek,
})

describe('SaglikSeridi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('alti bolumu, goreli zamani ve sorun rozetlerini gosterir', async () => {
    saglikApi.getSaglik.mockResolvedValue({ data: { sections: {
      news: bolum(), cve: bolum(), kubernetes: bolum(), sre: bolum(),
      devtools: bolum({ silent_sources: ['Redis', 'RabbitMQ'] }), ai: bolum({ last_status: 'failure' }),
    } } })

    render(<SaglikSeridi />)

    expect(await screen.findByText('DevTools')).toBeInTheDocument()
    expect(screen.getByText('2 sessiz')).toBeInTheDocument()
    expect(screen.getByText('son tur hatalı')).toBeInTheDocument()
    expect(screen.getAllByText('ok')).toHaveLength(4)
    expect(screen.getAllByText('1 sa önce')).toHaveLength(6)
    expect(screen.getByTitle('Sessiz: Redis, RabbitMQ')).toBeInTheDocument()
  })

  it('13 saatten eski son basari "bayat", hic basari yoksa "veri yok" rozeti alir', async () => {
    saglikApi.getSaglik.mockResolvedValue({ data: { sections: {
      news: bolum(), cve: bolum(), kubernetes: bolum(), sre: bolum(),
      devtools: bolum({ last_success_at: new Date(Date.now() - 13 * 3600 * 1000).toISOString() }),
      ai: bolum({ last_success_at: null }),
    } } })

    render(<SaglikSeridi />)

    expect(await screen.findByText('bayat')).toBeInTheDocument()
    expect(screen.getByText('veri yok')).toBeInTheDocument()
    expect(screen.getAllByText('ok')).toHaveLength(4)
  })

  it('sessiz kaynak, bayatlik rozetinden once gelir', async () => {
    saglikApi.getSaglik.mockResolvedValue({ data: { sections: {
      news: bolum({ silent_sources: ['Seq'], last_success_at: new Date(Date.now() - 20 * 3600 * 1000).toISOString() }),
      cve: bolum(), kubernetes: bolum(), sre: bolum(), devtools: bolum(), ai: bolum(),
    } } })

    render(<SaglikSeridi />)

    expect(await screen.findByText('1 sessiz')).toBeInTheDocument()
    expect(screen.queryByText('bayat')).not.toBeInTheDocument()
  })

  it('istek basarisizsa sessiz bir uyari gosterir', async () => {
    saglikApi.getSaglik.mockRejectedValue(new Error('500'))

    render(<SaglikSeridi />)

    expect(await screen.findByText('Sağlık bilgisi alınamadı.')).toBeInTheDocument()
  })
})
