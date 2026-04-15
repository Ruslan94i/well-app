import type { DailyCauseBand, EventInterval, HierarchicalEventTracks, TimeSeriesPoint } from '@/types/timeseries'

function clampIndex(index: number, maxIndex: number): number {
  return Math.max(0, Math.min(index, maxIndex))
}

function getRangeDates(data: TimeSeriesPoint[], startIndex: number, endIndex: number) {
  const maxIndex = data.length - 1
  const from = data[clampIndex(startIndex, maxIndex)]?.date
  const to = data[clampIndex(endIndex, maxIndex)]?.date

  return {
    startDate: from ?? '',
    endDate: to ?? ''
  }
}

function getScaledIndex(data: TimeSeriesPoint[], ratio: number): number {
  return clampIndex(Math.round((data.length - 1) * ratio), data.length - 1)
}

function createInterval(
  data: TimeSeriesPoint[],
  id: string,
  startRatio: number,
  endRatio: number,
  label: string,
  color: string
): EventInterval {
  return {
    id,
    ...getRangeDates(data, getScaledIndex(data, startRatio), getScaledIndex(data, endRatio)),
    label,
    color
  }
}

function average(values: Array<number | null>): number {
  const filteredValues = values.filter((value): value is number => Number.isFinite(value))
  if (filteredValues.length === 0) {
    return 0
  }

  return filteredValues.reduce((sum, value) => sum + value, 0) / filteredValues.length
}

function getSlice(data: TimeSeriesPoint[], startRatio: number, endRatio: number): TimeSeriesPoint[] {
  const startIndex = getScaledIndex(data, startRatio)
  const endIndex = getScaledIndex(data, endRatio)
  return data.slice(startIndex, endIndex + 1)
}

function detectScenario(data: TimeSeriesPoint[]): 'degradation' | 'unstable' | 'water' {
  const earlyWaterCut = average(getSlice(data, 0.0, 0.16).map((point) => point.water_cut))
  const lateWaterCut = average(getSlice(data, 0.82, 1.0).map((point) => point.water_cut))
  const midQliq = average(getSlice(data, 0.38, 0.5).map((point) => point.qliq))
  const earlyQliq = average(getSlice(data, 0.0, 0.12).map((point) => point.qliq))
  const lateQliq = average(getSlice(data, 0.55, 0.68).map((point) => point.qliq))
  const frequencyValues = data
    .map((point) => point.esp_frequency)
    .filter((value): value is number => Number.isFinite(value))
  const minFrequency = frequencyValues.length > 0 ? Math.min(...frequencyValues) : Number.POSITIVE_INFINITY

  if (lateWaterCut - earlyWaterCut > 13) {
    return 'water'
  }

  if (minFrequency < 46.6 || midQliq < earlyQliq * 0.9) {
    return 'unstable'
  }

  if (lateQliq > midQliq + 2.5) {
    return 'degradation'
  }

  return 'degradation'
}

export function generateMockEventTracks(data: TimeSeriesPoint[]): HierarchicalEventTracks {
  if (data.length === 0) {
    return {
      installedEspPeriods: [],
      dailyCauses: [],
      opzEvents: [],
      espWashEvents: [],
      modelEventIntervals: [],
      modelRootCauseIntervals: []
    }
  }

  const scenario = detectScenario(data)
  const scenarioRootCauses: Record<typeof scenario, EventInterval[]> = {
    degradation: [
      createInterval(data, 'model-cause-1', 0.18, 0.41, 'деградация ЭЦН', '#e7d7c8'),
      createInterval(data, 'model-cause-2', 0.43, 0.49, 'останов ВСП', '#d9dee7'),
      createInterval(data, 'model-cause-3', 0.53, 0.67, 'эффект ОПЗ', '#d8efe6'),
      createInterval(data, 'model-cause-4', 0.74, 0.96, 'прорыв воды', '#d8e6ff')
    ],
    unstable: [
      createInterval(data, 'model-cause-1', 0.2, 0.34, 'нестабильная работа', '#e5defa'),
      createInterval(data, 'model-cause-2', 0.35, 0.5, 'останов ВСП', '#d9dee7'),
      createInterval(data, 'model-cause-3', 0.58, 0.79, 'замена ЭЦН', '#d7edf2'),
      createInterval(data, 'model-cause-4', 0.8, 0.96, 'эффект ОПЗ', '#d8efe6')
    ],
    water: [
      createInterval(data, 'model-cause-1', 0.14, 0.28, 'деградация ЭЦН', '#e7d7c8'),
      createInterval(data, 'model-cause-2', 0.39, 0.56, 'эффект ОПЗ', '#d8efe6'),
      createInterval(data, 'model-cause-3', 0.57, 0.94, 'прорыв воды', '#d8e6ff'),
      createInterval(data, 'model-cause-4', 0.94, 0.99, 'смена режима', '#e3e8ef')
    ]
  }

  const scenarioEvents: Record<typeof scenario, EventInterval[]> = {
    degradation: [
      createInterval(data, 'model-event-1', 0.27, 0.3, 'локальное снижение дебита', '#f2c6a8'),
      createInterval(data, 'model-event-2', 0.36, 0.39, 'изменение частоты', '#c9d7f8'),
      createInterval(data, 'model-event-3', 0.445, 0.462, 'кратковременный останов', '#cfd6e3'),
      createInterval(data, 'model-event-4', 0.53, 0.545, 'ОПЗ', '#bfe7d8'),
      createInterval(data, 'model-event-5', 0.56, 0.595, 'временное восстановление', '#d3f2b6'),
      createInterval(data, 'model-event-6', 0.82, 0.85, 'локальная нестабильность', '#d5d8ff')
    ],
    unstable: [
      createInterval(data, 'model-event-1', 0.23, 0.25, 'локальная нестабильность', '#d5d8ff'),
      createInterval(data, 'model-event-2', 0.3, 0.33, 'изменение частоты', '#c9d7f8'),
      createInterval(data, 'model-event-3', 0.41, 0.44, 'кратковременный останов', '#cfd6e3'),
      createInterval(data, 'model-event-4', 0.6, 0.63, 'локальное снижение дебита', '#f2c6a8'),
      createInterval(data, 'model-event-5', 0.69, 0.72, 'временное восстановление', '#d3f2b6'),
      createInterval(data, 'model-event-6', 0.84, 0.87, 'ОПЗ', '#bfe7d8')
    ],
    water: [
      createInterval(data, 'model-event-1', 0.2, 0.23, 'локальное снижение дебита', '#f2c6a8'),
      createInterval(data, 'model-event-2', 0.44, 0.465, 'ОПЗ', '#bfe7d8'),
      createInterval(data, 'model-event-3', 0.49, 0.53, 'временное восстановление', '#d3f2b6'),
      createInterval(data, 'model-event-4', 0.67, 0.69, 'локальная нестабильность', '#d5d8ff'),
      createInterval(data, 'model-event-5', 0.79, 0.82, 'локальное снижение дебита', '#f4d2bf'),
      createInterval(data, 'model-event-6', 0.95, 0.97, 'изменение частоты', '#c9d7f8')
    ]
  }

  const modelRootCauseIntervals = scenarioRootCauses[scenario]
  const modelEventIntervals = scenarioEvents[scenario]

  const dailyCauseByRoot = new Map<string, { label: string; color: string }>([
    ['деградация ЭЦН', { label: 'деградация ЭЦН', color: '#dfd1c4' }],
    ['нестабильная работа', { label: 'нестабильная работа', color: '#e5defa' }],
    ['останов ВСП', { label: 'простои ВСП', color: '#d8dee9' }],
    ['эффект ОПЗ', { label: 'последействие ОПЗ', color: '#d5ede3' }],
    ['прорыв воды', { label: 'водоприток', color: '#d4e4ff' }],
    ['замена ЭЦН', { label: 'замена ЭЦН', color: '#d7edf2' }],
    ['смена режима', { label: 'смена режима', color: '#e3e8ef' }]
  ])

  const dailyCauseByEvent = new Map<string, { label: string; color: string }>([
    ['локальное снижение дебита', { label: 'локальное снижение дебита', color: '#ead4c5' }],
    ['изменение частоты', { label: 'изменение частоты ЭЦН', color: '#d7e2fb' }],
    ['кратковременный останов', { label: 'кратковременный останов', color: '#d7dce5' }],
    ['ОПЗ', { label: 'технологическая операция', color: '#cae6dd' }],
    ['временное восстановление', { label: 'временное восстановление', color: '#ddf0cc' }],
    ['локальная нестабильность', { label: 'локальная нестабильность', color: '#e2e2fb' }]
  ])

  const fallbackDailyCause = { label: 'стабильная работа', color: '#e2e8f0' }

  const dailyCauses: DailyCauseBand[] = data.map((point) => {
    const activeRootCause = modelRootCauseIntervals.find((interval) => interval.startDate <= point.date && point.date <= interval.endDate)
    const activeEvent = modelEventIntervals.find((interval) => interval.startDate <= point.date && point.date <= interval.endDate)
    const causeItem =
      (activeEvent && dailyCauseByEvent.get(activeEvent.label)) ||
      (activeRootCause && dailyCauseByRoot.get(activeRootCause.label)) ||
      fallbackDailyCause

    return {
      date: point.date,
      label: causeItem.label,
      color: causeItem.color
    }
  })

  const installedEspPeriods = [
    {
      id: 'esp-1',
      espId: 'ESP-A315',
      ...getRangeDates(data, 0, getScaledIndex(data, scenario === 'unstable' ? 0.56 : 0.47))
    },
    {
      id: 'esp-2',
      espId: scenario === 'water' ? 'ESP-C208' : 'ESP-B412',
      ...getRangeDates(data, getScaledIndex(data, scenario === 'unstable' ? 0.57 : 0.48), data.length - 1)
    }
  ]

  const opzEvents =
    scenario === 'unstable'
      ? [
          {
            id: 'opz-1',
            date: data[getScaledIndex(data, 0.84)]?.date ?? data[0]?.date ?? '',
            operationType: 'обработка призабойной зоны',
            comment: 'ОПЗ выполнена после стабилизации режима и замены ЭЦН.'
          }
        ].filter((item) => item.date)
      : [
          {
            id: 'opz-1',
            date: data[getScaledIndex(data, scenario === 'water' ? 0.44 : 0.53)]?.date ?? data[0]?.date ?? '',
            operationType: 'кислотная обработка',
            comment: 'ОПЗ с ожидаемым краткосрочным ростом дебита и последующим затуханием эффекта.'
          },
          {
            id: 'opz-2',
            date: data[getScaledIndex(data, scenario === 'water' ? 0.49 : 0.56)]?.date ?? data[0]?.date ?? '',
            operationType: 'освоение после ОПЗ',
            comment: 'Стабилизация режима после обработки и вывода на рабочую частоту.'
          }
        ].filter((item) => item.date)

  return {
    installedEspPeriods,
    dailyCauses,
    opzEvents,
    espWashEvents: [],
    modelEventIntervals,
    modelRootCauseIntervals
  }
}
