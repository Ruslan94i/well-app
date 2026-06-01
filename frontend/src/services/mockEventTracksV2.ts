import type { DailyCauseBand, EventInterval, HierarchicalEventTracks, OpzEventFlag, TimeSeriesPoint } from '@/types/timeseries'

type Scenario = 'degradation' | 'unstable' | 'water'

interface ScenarioSegment {
  id: string
  startRatio: number
  endRatio: number
  label: string
}

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

function detectScenario(data: TimeSeriesPoint[]): Scenario {
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

const episodeColorMap: Record<string, string> = {
  'НУР': '#d7c6a4',
  'Кратковременная нестабильность': '#b6a7eb',
  'Краткий простой': '#a8b0bf',
  'Локальное падение дебита': '#d39b74',
  'Временное восстановление дебита': '#9fce86',
  'Скачок частоты ЭЦН': '#7db7ec',
  'Кратковременный рост обводненности': '#90c2e8',
  'Эффект после вмешательства': '#86c6b1'
}

const dailyCauseByEpisode = new Map<string, { label: string; color: string }>([
  ['НУР', { label: 'НУР', color: '#bda98a' }],
  ['Кратковременная нестабильность', { label: 'кратковременная нестабильность', color: '#9a8dd2' }],
  ['Краткий простой', { label: 'краткий простой', color: '#8d96a6' }],
  ['Локальное падение дебита', { label: 'локальное падение дебита', color: '#bf8f6f' }],
  ['Временное восстановление дебита', { label: 'временное восстановление', color: '#8cbc79' }],
  ['Скачок частоты ЭЦН', { label: 'изменение частоты ЭЦН', color: '#74a9d8' }],
  ['Кратковременный рост обводненности', { label: 'краткий рост обводненности', color: '#7fb8d9' }],
  ['Эффект после вмешательства', { label: 'локальный эффект вмешательства', color: '#78b6a2' }]
])

function createInterval(
  data: TimeSeriesPoint[],
  segment: ScenarioSegment
): EventInterval | null {
  const interval = getRangeDates(data, getScaledIndex(data, segment.startRatio), getScaledIndex(data, segment.endRatio))
  if (!interval.startDate || !interval.endDate) {
    return null
  }

  return {
    id: segment.id,
    ...interval,
    label: segment.label,
    color: episodeColorMap[segment.label] ?? '#cbd5e1'
  }
}

function createScenarioEpisodes(data: TimeSeriesPoint[], scenario: Scenario): EventInterval[] {
  const episodesByScenario: Record<Scenario, ScenarioSegment[]> = {
    degradation: [
      { id: 'episode-1', startRatio: 0.24, endRatio: 0.28, label: 'Локальное падение дебита' },
      { id: 'episode-2', startRatio: 0.36, endRatio: 0.39, label: 'Скачок частоты ЭЦН' },
      { id: 'episode-3', startRatio: 0.43, endRatio: 0.47, label: 'Краткий простой' },
      { id: 'episode-4', startRatio: 0.52, endRatio: 0.55, label: 'Временное восстановление дебита' },
      { id: 'episode-5', startRatio: 0.62, endRatio: 0.65, label: 'Эффект после вмешательства' },
      { id: 'episode-6', startRatio: 0.78, endRatio: 0.82, label: 'Кратковременный рост обводненности' },
      { id: 'episode-7', startRatio: 0.9, endRatio: 0.94, label: 'НУР' }
    ],
    unstable: [
      { id: 'episode-1', startRatio: 0.16, endRatio: 0.19, label: 'Кратковременная нестабильность' },
      { id: 'episode-2', startRatio: 0.28, endRatio: 0.31, label: 'Скачок частоты ЭЦН' },
      { id: 'episode-3', startRatio: 0.36, endRatio: 0.39, label: 'Локальное падение дебита' },
      { id: 'episode-4', startRatio: 0.44, endRatio: 0.49, label: 'Краткий простой' },
      { id: 'episode-5', startRatio: 0.58, endRatio: 0.62, label: 'Временное восстановление дебита' },
      { id: 'episode-6', startRatio: 0.76, endRatio: 0.8, label: 'НУР' },
      { id: 'episode-7', startRatio: 0.86, endRatio: 0.9, label: 'Эффект после вмешательства' }
    ],
    water: [
      { id: 'episode-1', startRatio: 0.2, endRatio: 0.23, label: 'Локальное падение дебита' },
      { id: 'episode-2', startRatio: 0.32, endRatio: 0.35, label: 'Эффект после вмешательства' },
      { id: 'episode-3', startRatio: 0.42, endRatio: 0.46, label: 'Временное восстановление дебита' },
      { id: 'episode-4', startRatio: 0.56, endRatio: 0.6, label: 'Кратковременный рост обводненности' },
      { id: 'episode-5', startRatio: 0.68, endRatio: 0.72, label: 'НУР' },
      { id: 'episode-6', startRatio: 0.78, endRatio: 0.82, label: 'Кратковременная нестабильность' },
      { id: 'episode-7', startRatio: 0.92, endRatio: 0.96, label: 'Скачок частоты ЭЦН' }
    ]
  }

  return episodesByScenario[scenario]
    .map((segment) => createInterval(data, segment))
    .filter((item): item is EventInterval => Boolean(item))
}

function buildDailyCauses(data: TimeSeriesPoint[], episodes: EventInterval[]): DailyCauseBand[] {
  const fallbackDailyCause = { label: 'стабильная работа', color: '#6b7c93' }

  return data.map((point) => {
    const activeEpisode = episodes.find((interval) => interval.startDate <= point.date && point.date <= interval.endDate)
    const causeItem = (activeEpisode && dailyCauseByEpisode.get(activeEpisode.label)) || fallbackDailyCause

    return {
      date: point.date,
      label: causeItem.label,
      color: causeItem.color
    }
  })
}

function buildInstalledEspPeriods(data: TimeSeriesPoint[], scenario: Scenario): HierarchicalEventTracks['installedEspPeriods'] {
  const replacementIndex = getScaledIndex(data, scenario === 'unstable' ? 0.5 : scenario === 'water' ? 0.47 : 0.48)

  return [
    {
      id: 'esp-1',
      espId: scenario === 'water' ? 'ESP-A315' : 'ESP-A312',
      ...getRangeDates(data, 0, replacementIndex)
    },
    {
      id: 'esp-2',
      espId: scenario === 'unstable' ? 'ESP-B428' : scenario === 'water' ? 'ESP-C208' : 'ESP-B412',
      ...getRangeDates(data, replacementIndex + 1, data.length - 1)
    }
  ].filter((item) => item.startDate && item.endDate)
}

function buildOpzEvents(data: TimeSeriesPoint[], scenario: Scenario): OpzEventFlag[] {
  const eventsByScenario: Record<Scenario, Array<{ ratio: number; operationType: string; comment: string }>> = {
    degradation: [
      {
        ratio: 0.63,
        operationType: 'кислотная обработка',
        comment: 'ОПЗ проведена на фоне снижения подачи с ожидаемым кратковременным восстановлением.'
      },
      {
        ratio: 0.68,
        operationType: 'освоение после ОПЗ',
        comment: 'Контроль стабилизации после вывода скважины на рабочую частоту.'
      }
    ],
    unstable: [
      {
        ratio: 0.85,
        operationType: 'обработка призабойной зоны',
        comment: 'ОПЗ выполнена после стабилизации работы нового ЭЦН.'
      }
    ],
    water: [
      {
        ratio: 0.32,
        operationType: 'кислотная обработка',
        comment: 'ОПЗ проведена в попытке поддержать дебит до устойчивого роста воды.'
      },
      {
        ratio: 0.38,
        operationType: 'освоение после ОПЗ',
        comment: 'Кратковременный эффект после вмешательства и переход к новой динамике.'
      }
    ]
  }

  return eventsByScenario[scenario]
    .map((item, index) => ({
      id: `opz-${index + 1}`,
      date: data[getScaledIndex(data, item.ratio)]?.date ?? '',
      operationType: item.operationType,
      comment: item.comment
    }))
    .filter((item) => item.date)
}

function buildEspWashEvents(data: TimeSeriesPoint[], scenario: Scenario): OpzEventFlag[] {
  const eventsByScenario: Record<Scenario, Array<{ ratio: number; comment: string }>> = {
    degradation: [
      {
        ratio: 0.34,
        comment: 'Промывка ЭЦН выполнена на фоне деградации подачи для снятия отложений и локального восстановления.'
      }
    ],
    unstable: [
      {
        ratio: 0.24,
        comment: 'Промывка ЭЦН назначена после серии нестабильных колебаний тока и подачи.'
      },
      {
        ratio: 0.73,
        comment: 'Контрольная промывка ЭЦН перед повторной стабилизацией работы.'
      }
    ],
    water: [
      {
        ratio: 0.22,
        comment: 'Промывка ЭЦН проведена до выраженного роста воды, на фоне локального падения дебита.'
      }
    ]
  }

  return eventsByScenario[scenario]
    .map((item, index) => ({
      id: `esp-wash-${index + 1}`,
      date: data[getScaledIndex(data, item.ratio)]?.date ?? '',
      operationType: 'Промывка ЭЦН',
      comment: item.comment
    }))
    .filter((item) => item.date)
}

export function generateMockEventTracks(data: TimeSeriesPoint[]): HierarchicalEventTracks {
  if (data.length === 0) {
    return {
      installedEspPeriods: [],
      dailyCauses: [],
      opzEvents: [],
      espWashEvents: [],
      gtmEvents: [],
      gdiEvents: [],
      modelEventIntervals: []
    }
  }

  const scenario = detectScenario(data)
  const modelEventIntervals = createScenarioEpisodes(data, scenario)
  const dailyCauses = buildDailyCauses(data, modelEventIntervals)
  const installedEspPeriods = buildInstalledEspPeriods(data, scenario)
  const opzEvents = buildOpzEvents(data, scenario)
  const espWashEvents = buildEspWashEvents(data, scenario)

  return {
    installedEspPeriods,
    dailyCauses,
    opzEvents,
    espWashEvents,
    gtmEvents: [],
    gdiEvents: [],
    modelEventIntervals
  }
}
