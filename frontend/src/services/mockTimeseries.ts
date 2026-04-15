import type { TimeSeriesPoint } from '@/types/timeseries'

type MockTimeseriesParams = {
  date_from?: string
  date_to?: string
}

type ScenarioConfig = {
  qliqStart: number
  qliqDecline: number
  degradationStart: number
  degradationDuration: number
  degradationAmp: number
  downtimeCenter: number
  downtimeSigma: number
  downtimeAmp: number
  replacementStart: number
  replacementDuration: number
  replacementAmp: number
  opzStart: number
  opzFadeStart: number
  opzAmp: number
  waterStart: number
  waterDuration: number
  waterAmp: number
  regimeStart: number
  regimeDuration: number
  regimeAmp: number
}

const DEFAULT_TOTAL_DAYS = 180
const DEFAULT_END_DATE = '2025-06-30'
const DAY_MS = 86400000

function hashWellId(wellId: string): number {
  let hash = 2166136261

  for (let index = 0; index < wellId.length; index += 1) {
    hash ^= wellId.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }

  return hash >>> 0
}

function createRng(seed: number): () => number {
  let state = seed || 1

  return () => {
    state += 0x6d2b79f5
    let next = state
    next = Math.imul(next ^ (next >>> 15), next | 1)
    next ^= next + Math.imul(next ^ (next >>> 7), next | 61)
    return ((next ^ (next >>> 14)) >>> 0) / 4294967296
  }
}

function round(value: number): number {
  return Number(value.toFixed(2))
}

function clamp(value: number, min: number, max?: number): number {
  if (typeof max === 'number') {
    return Math.min(Math.max(value, min), max)
  }

  return Math.max(value, min)
}

function isoToTimestamp(value: string): number {
  return new Date(`${value}T00:00:00Z`).getTime()
}

function timestampToIso(value: number): string {
  return new Date(value).toISOString().slice(0, 10)
}

function shiftIsoDate(value: string, deltaDays: number): string {
  return timestampToIso(isoToTimestamp(value) + deltaDays * DAY_MS)
}

function getDateBounds(params: MockTimeseriesParams): { dateFrom: string; dateTo: string } {
  const dateTo = params.date_to ?? DEFAULT_END_DATE
  const dateFrom =
    params.date_from ?? shiftIsoDate(dateTo, -(DEFAULT_TOTAL_DAYS - 1))

  if (isoToTimestamp(dateFrom) <= isoToTimestamp(dateTo)) {
    return { dateFrom, dateTo }
  }

  return { dateFrom: dateTo, dateTo: dateFrom }
}

function getScenario(seed: number): ScenarioConfig {
  const variant = seed % 3

  switch (variant) {
    case 0:
      return {
        qliqStart: 124,
        qliqDecline: 0.09,
        degradationStart: 0.2,
        degradationDuration: 0.22,
        degradationAmp: 7.5,
        downtimeCenter: 0.46,
        downtimeSigma: 0.02,
        downtimeAmp: 20,
        replacementStart: 0.48,
        replacementDuration: 0.05,
        replacementAmp: 8,
        opzStart: 0.53,
        opzFadeStart: 0.62,
        opzAmp: 6,
        waterStart: 0.7,
        waterDuration: 0.19,
        waterAmp: 14,
        regimeStart: 0.82,
        regimeDuration: 0.07,
        regimeAmp: 2.2
      }
    case 1:
      return {
        qliqStart: 118,
        qliqDecline: 0.07,
        degradationStart: 0.32,
        degradationDuration: 0.12,
        degradationAmp: 4.8,
        downtimeCenter: 0.3,
        downtimeSigma: 0.03,
        downtimeAmp: 10.5,
        replacementStart: 0.57,
        replacementDuration: 0.05,
        replacementAmp: 5.5,
        opzStart: 0.66,
        opzFadeStart: 0.74,
        opzAmp: 3.8,
        waterStart: 0.77,
        waterDuration: 0.14,
        waterAmp: 7.5,
        regimeStart: 0.4,
        regimeDuration: 0.06,
        regimeAmp: 3
      }
    default:
      return {
        qliqStart: 121,
        qliqDecline: 0.08,
        degradationStart: 0.12,
        degradationDuration: 0.17,
        degradationAmp: 5.2,
        downtimeCenter: 0.66,
        downtimeSigma: 0.02,
        downtimeAmp: 8,
        replacementStart: 0.68,
        replacementDuration: 0.04,
        replacementAmp: 4,
        opzStart: 0.39,
        opzFadeStart: 0.49,
        opzAmp: 4.8,
        waterStart: 0.51,
        waterDuration: 0.24,
        waterAmp: 16,
        regimeStart: 0.82,
        regimeDuration: 0.08,
        regimeAmp: 3.6
      }
  }
}

function smoothStep(position: number, start: number, duration: number): number {
  const scaled = clamp((position - start) / Math.max(duration, 1e-6), 0, 1)
  return scaled * scaled * (3 - 2 * scaled)
}

function gaussianPulse(position: number, center: number, sigma: number): number {
  const normalized = (position - center) / Math.max(sigma, 1e-6)
  return Math.exp(-0.5 * normalized * normalized)
}

function buildDates(dateFrom: string, dateTo: string): string[] {
  const dates: string[] = []
  let cursor = isoToTimestamp(dateFrom)
  const end = isoToTimestamp(dateTo)

  while (cursor <= end) {
    dates.push(timestampToIso(cursor))
    cursor += DAY_MS
  }

  return dates
}

export function generateMockTimeseries(
  wellId: string,
  params: MockTimeseriesParams = {}
): TimeSeriesPoint[] {
  const { dateFrom, dateTo } = getDateBounds(params)
  const dates = buildDates(dateFrom, dateTo)
  const seed = hashWellId(wellId)
  const scenario = getScenario(seed)
  const random = createRng(seed)

  return dates.map((date, index) => {
    const lastIndex = Math.max(dates.length - 1, 1)
    const progress = index / lastIndex

    const degradation = smoothStep(progress, scenario.degradationStart, scenario.degradationDuration)
    const downtime = gaussianPulse(progress, scenario.downtimeCenter, scenario.downtimeSigma)
    const replacementReset = smoothStep(progress, scenario.replacementStart, scenario.replacementDuration)
    const opzEffect = clamp(
      (progress >= scenario.opzStart
        ? 1 - Math.exp(-9 * (progress - scenario.opzStart))
        : 0) -
        (progress >= scenario.opzFadeStart
          ? 1 - Math.exp(-5 * (progress - scenario.opzFadeStart))
          : 0),
      0
    )
    const waterBreakthrough = smoothStep(progress, scenario.waterStart, scenario.waterDuration)
    const regimeShift = smoothStep(progress, scenario.regimeStart, scenario.regimeDuration)

    const qliqBase =
      scenario.qliqStart -
      scenario.qliqDecline * index -
      scenario.degradationAmp * degradation -
      scenario.downtimeAmp * downtime +
      scenario.replacementAmp * replacementReset +
      scenario.opzAmp * opzEffect -
      0.32 * scenario.waterAmp * waterBreakthrough -
      0.9 * scenario.regimeAmp * regimeShift +
      0.9 * Math.sin(index / 17) +
      (random() - 0.5) * 1.1
    const qliq = clamp(qliqBase, 62)

    const waterCut = clamp(
      23 +
        0.035 * index +
        0.9 * degradation -
        1.1 * opzEffect +
        scenario.waterAmp * waterBreakthrough +
        scenario.regimeAmp * regimeShift +
        (random() - 0.5) * 1.2,
      8,
      92
    )

    const qoil = clamp(
      Math.min(
        qliq * 0.95,
        qliq * (1 - waterCut / 100) -
          1.8 * degradation +
          2.2 * opzEffect -
          (2.2 + 0.08 * scenario.waterAmp) * waterBreakthrough +
          (random() - 0.5) * 1.3
      ),
      12
    )

    const gasFactor = clamp(
      198 +
        0.03 * index -
        6 * degradation -
        10 * downtime +
        8.5 * replacementReset +
        14 * opzEffect +
        12 * waterBreakthrough +
        5 * regimeShift +
        4 * Math.sin(index / 29) +
        (random() - 0.5) * 6.4,
      145,
      285
    )

    const qgas = clamp(qoil * gasFactor, 1800)
    const gasLiquidFactor = qgas / Math.max(qliq, 1)
    const qliqVfm = clamp(qliq * (1.006 + 0.004 * Math.sin(index / 23)) + (random() - 0.5) * 1.1, 60)
    const qliqWfm = clamp(qliq * (0.996 + 0.005 * Math.cos(index / 19)) + (random() - 0.5) * 0.9, 60)
    const intakePressure = round(
      116.5 -
        0.018 * index +
        (2 + 0.18 * scenario.degradationAmp) * degradation -
        (3.8 + 0.22 * scenario.downtimeAmp) * downtime -
        (1.2 + 0.16 * scenario.replacementAmp) * replacementReset +
        (1.8 + 0.14 * scenario.waterAmp) * waterBreakthrough +
        0.7 * scenario.regimeAmp * regimeShift +
        1.1 * Math.sin(index / 21) +
        (random() - 0.5) * 1.4
    )
    const espFrequency = clamp(
      49.6 -
        0.18 * degradation -
        (1 + 0.12 * scenario.downtimeAmp) * downtime +
        0.14 * scenario.replacementAmp * replacementReset -
        0.025 * scenario.waterAmp * waterBreakthrough +
        0.1 * scenario.regimeAmp * regimeShift +
        (random() - 0.5) * 0.16,
      43.5,
      52.5
    )
    const load = clamp(
      61.5 -
        0.025 * index -
        (0.9 + 0.12 * scenario.degradationAmp) * degradation -
        (2.8 + 0.18 * scenario.downtimeAmp) * downtime +
        scenario.replacementAmp * 0.24 * replacementReset +
        0.2 * scenario.opzAmp * opzEffect +
        (0.4 + 0.08 * scenario.waterAmp) * waterBreakthrough +
        0.9 * Math.sin(index / 26) +
        (random() - 0.5) * 0.9,
      42,
      74
    )

    return {
      date,
      qliq: round(qliq),
      qoil: round(qoil),
      qgas: round(qgas),
      gas_factor: round(gasFactor),
      gas_liquid_factor: round(gasLiquidFactor),
      qliq_wfm: round(qliqWfm),
      qliq_vfm: round(qliqVfm),
      water_cut: round(waterCut),
      intake_pressure: intakePressure,
      esp_frequency: round(espFrequency),
      load: round(load)
    }
  })
}
