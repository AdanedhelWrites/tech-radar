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
      devtools: bolum({ silent_sources: ['MinIO', 'RabbitMQ'] }), ai: bolum({ last_status: 'failure' }),
    } } })

    render(<SaglikSeridi />)

    expect(await screen.findByText('DevTools')).toBeInTheDocument()
    expect(screen.getByText('2 sessiz')).toBeInTheDocument()
    expect(screen.getByText('son tur hatalı')).toBeInTheDocument()
    expect(screen.getAllByText('ok')).toHaveLength(4)
    expect(screen.getAllByText('1 sa önce')).toHaveLength(6)
    expect(screen.getByTitle('Sessiz: MinIO, RabbitMQ')).toBeInTheDocument()
  })

  it('istek basarisizsa sessiz bir uyari gosterir', async () => {
    saglikApi.getSaglik.mockRejectedValue(new Error('500'))

    render(<SaglikSeridi />)

    expect(await screen.findByText('Sağlık bilgisi alınamadı.')).toBeInTheDocument()
  })
})
