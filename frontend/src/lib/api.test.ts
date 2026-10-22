import { describe, expect, it, beforeEach } from 'vitest'
import { money, queryString } from './api'

describe('formatting helpers', () => {
  beforeEach(() => { localStorage.clear() })
  it('builds clean filter query strings', () => {
    expect(queryString({year:2026,quarter:2,activity_id:'act-1',client_id:'',optional:null})).toBe('?year=2026&quarter=2&activity_id=act-1')
  })
  it('formats XOF as whole CFA francs', () => {
    expect(money(1250000)).toBe('1\u202f250\u202f000 FCFA')
  })
  it('applies the configured manual display conversion', () => {
    localStorage.setItem('finpilot_currency','EUR')
    localStorage.setItem('finpilot_fx_rate','655.957')
    expect(money(655957)).toContain('1')
    expect(money(655957)).toContain('EUR')
  })
})
