import type { DailyCauseBand, EventInterval, HierarchicalEventTracks, OpzEventFlag, TimeSeriesPoint } from '@/types/timeseries'

type Scenario = 'degradation' | 'unstable' | 'water'

interface ScenarioSegment {
  id: string
  startRatio: number
  endRatio: number
  label: string
}

interface EpisodeTemplate {
  id: string
  regimeId: string
  startOffsetRatio: number
  durationRatio: number
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

const regimeColorMap: Record<string, string> = {
  'Стабильная работа': '#8aa0b6',
  'Деградация ЭЦН': '#b88b68',
  'Рост обводненности': '#7aa7d6',
  'Прорыв воды': '#5f8fd8',
  'Нестабильный режим': '#8a7be0',
  'Эффект после ОПЗ': '#6ba88f',
  'Ограничение режима эксплуатации': '#7d8795',
  'ВСП / простой': '#798496',
  'После смены ЭЦН': '#5fa8c9'
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

const dailyCauseByRegime = new Map<string, { label: string; color: string }>([
  ['Стабильная работа', { label: 'стабильная эксплуатация', color: '#73859c' }],
  ['Деградация ЭЦН', { label: 'снижение эффективности ЭЦН', color: '#8d745f' }],
  ['Рост обводненности', { label: 'устойчивый рост обводненности', color: '#6f9ec7' }],
  ['Прорыв воды', { label: 'водоприток', color: '#5b86c7' }],
  ['Нестабильный режим', { label: 'нестабильный режим', color: '#8276c5' }],
  ['Эффект после ОПЗ', { label: 'последействие ОПЗ', color: '#5f9d88' }],
  ['Ограничение режима эксплуатации', { label: 'ограничение эксплуатации', color: '#727b88' }],
  ['ВСП / простой', { label: 'простой ВСП', color: '#697382' }],
  ['После смены ЭЦН', { label: 'период после смены ЭЦН', color: '#5f96b0' }]
])

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

function createIntervalFromIndexes(
  data: TimeSeriesPoint[],
  id: string,
  startIndex: number,
  endIndex: number,
  label: string,
  color: string
): EventInterval {
  return {
    id,
    ...getRangeDates(data, startIndex, endIndex),
    label,
    color
  }
}

function createSegments(
  data: TimeSeriesPoint[],
  segments: ScenarioSegment[],
  palette: Record<string, string>
): EventInterval[] {
  return segments
    .map((segment) =>
      createIntervalFromIndexes(
        data,
        segment.id,
        getScaledIndex(data, segment.startRatio),
        getScaledIndex(data, segment.endRatio),
        segment.label,
        palette[segment.label] ?? '#94a3b8'
      )
    )
    .filter((item) => item.startDate && item.endDate)
}

function createEpisodesInsideRegimes(
  data: TimeSeriesPoint[],
  regimes: EventInterval[],
  templates: EpisodeTemplate[]
): EventInterval[] {
  return templates.flatMap((template) => {
    const regime = regimes.find((item) => item.id === template.regimeId)
    if (!regime) {
      return []
    }

    const regimeStartIndex = data.findIndex((point) => point.date === regime.startDate)
    const regimeEndIndex = data.findIndex((point) => point.date === regime.endDate)
    if (regimeStartIndex < 0 || regimeEndIndex < 0 || regimeEndIndex <= regimeStartIndex) {
      return []
    }

    const regimeLength = regimeEndIndex - regimeStartIndex + 1
    const episodeStartIndex = clampIndex(
      regimeStartIndex + Math.floor((regimeLength - 1) * template.startOffsetRatio),
      regimeEndIndex
    )
    const episodeDuration = Math.max(1, Math.floor(regimeLength * template.durationRatio))
    const episodeEndIndex = clampIndex(episodeStartIndex + episodeDuration - 1, regimeEndIndex)

    return [
      createIntervalFromIndexes(
        data,
        template.id,
        episodeStartIndex,
        episodeEndIndex,
        template.label,
        episodeColorMap[template.label] ?? '#cbd5e1'
      )
    ]
  })
}

function createScenarioRegimes(data: TimeSeriesPoint[], scenario: Scenario): EventInterval[] {
  const segmentsByScenario: Record<Scenario, ScenarioSegment[]> = {
    degradation: [
      { id: 'regime-1', startRatio: 0.0, endRatio: 0.16, label: 'Стабильная работа' },
      { id: 'regime-2', startRatio: 0.17, endRatio: 0.39, label: 'Деградация ЭЦН' },
      { id: 'regime-3', startRatio: 0.4, endRatio: 0.47, label: 'ВСП / простой' },
      { id: 'regime-4', startRatio: 0.48, endRatio: 0.61, label: 'После смены ЭЦН' },
      { id: 'regime-5', startRatio: 0.62, endRatio: 0.76, label: 'Эффект после ОПЗ' },
      { id: 'regime-6', startRatio: 0.77, endRatio: 0.88, label: 'Рост обводненности' },
      { id: 'regime-7', startRatio: 0.89, endRatio: 1.0, label: 'Прорыв воды' }
    ],
    unstable: [
      { id: 'regime-1', startRatio: 0.0, endRatio: 0.13, label: 'Стабильная работа' },
      { id: 'regime-2', startRatio: 0.14, endRatio: 0.31, label: 'Нестабильный режим' },
      { id: 'regime-3', startRatio: 0.32, endRatio: 0.42, label: 'Ограничение режима эксплуатации' },
      { id: 'regime-4', startRatio: 0.43, endRatio: 0.5, label: 'ВСП / простой' },
      { id: 'regime-5', startRatio: 0.51, endRatio: 0.71, label: 'После смены ЭЦН' },
      { id: 'regime-6', startRatio: 0.72, endRatio: 0.83, label: 'Нестабильный режим' },
      { id: 'regime-7', startRatio: 0.84, endRatio: 1.0, label: 'Эффект после ОПЗ' }
    ],
    water: [
      { id: 'regime-1', startRatio: 0.0, endRatio: 0.14, label: 'Стабильная работа' },
      { id: 'regime-2', startRatio: 0.15, endRatio: 0.29, label: 'Деградация ЭЦН' },
      { id: 'regime-3', startRatio: 0.3, endRatio: 0.46, label: 'Эффект после ОПЗ' },
      { id: 'regime-4', startRatio: 0.47, endRatio: 0.62, label: 'Рост обводненности' },
      { id: 'regime-5', startRatio: 0.63, endRatio: 0.9, label: 'Прорыв воды' },
      { id: 'regime-6', startRatio: 0.91, endRatio: 1.0, label: 'Ограничение режима эксплуатации' }
    ]
  }

  return createSegments(data, segmentsByScenario[scenario], regimeColorMap)
}

function createScenarioEpisodes(data: TimeSeriesPoint[], scenario: Scenario, regimes: EventInterval[]): EventInterval[] {
  const episodesByScenario: Record<Scenario, EpisodeTemplate[]> = {
    degradation: [
      { id: 'episode-1', regimeId: 'regime-2', startOffsetRatio: 0.32, durationRatio: 0.14, label: 'Локальное падение дебита' },
      { id: 'episode-2', regimeId: 'regime-2', startOffsetRatio: 0.72, durationRatio: 0.12, label: 'Скачок частоты ЭЦН' },
      { id: 'episode-3', regimeId: 'regime-3', startOffsetRatio: 0.18, durationRatio: 0.34, label: 'Краткий простой' },
      { id: 'episode-4', regimeId: 'regime-4', startOffsetRatio: 0.14, durationRatio: 0.16, label: 'Временное восстановление дебита' },
      { id: 'episode-5', regimeId: 'regime-5', startOffsetRatio: 0.08, durationRatio: 0.12, label: 'Эффект после вмешательства' },
      { id: 'episode-6', regimeId: 'regime-6', startOffsetRatio: 0.42, durationRatio: 0.12, label: 'Кратковременный рост обводненности' },
      { id: 'episode-7', regimeId: 'regime-7', startOffsetRatio: 0.24, durationRatio: 0.14, label: 'НУР' }
    ],
    unstable: [
      { id: 'episode-1', regimeId: 'regime-2', startOffsetRatio: 0.18, durationRatio: 0.12, label: 'Кратковременная нестабильность' },
      { id: 'episode-2', regimeId: 'regime-2', startOffsetRatio: 0.56, durationRatio: 0.12, label: 'Скачок частоты ЭЦН' },
      { id: 'episode-3', regimeId: 'regime-3', startOffsetRatio: 0.36, durationRatio: 0.16, label: 'Локальное падение дебита' },
      { id: 'episode-4', regimeId: 'regime-4', startOffsetRatio: 0.18, durationRatio: 0.28, label: 'Краткий простой' },
      { id: 'episode-5', regimeId: 'regime-5', startOffsetRatio: 0.14, durationRatio: 0.16, label: 'Временное восстановление дебита' },
      { id: 'episode-6', regimeId: 'regime-6', startOffsetRatio: 0.34, durationRatio: 0.12, label: 'НУР' },
      { id: 'episode-7', regimeId: 'regime-7', startOffsetRatio: 0.12, durationRatio: 0.12, label: 'Эффект после вмешательства' }
    ],
    water: [
      { id: 'episode-1', regimeId: 'regime-2', startOffsetRatio: 0.34, durationRatio: 0.12, label: 'Локальное падение дебита' },
      { id: 'episode-2', regimeId: 'regime-3', startOffsetRatio: 0.16, durationRatio: 0.12, label: 'Эффект после вмешательства' },
      { id: 'episode-3', regimeId: 'regime-3', startOffsetRatio: 0.52, durationRatio: 0.16, label: 'Временное восстановление дебита' },
      { id: 'episode-4', regimeId: 'regime-4', startOffsetRatio: 0.38, durationRatio: 0.14, label: 'Кратковременный рост обводненности' },
      { id: 'episode-5', regimeId: 'regime-5', startOffsetRatio: 0.18, durationRatio: 0.12, label: 'НУР' },
      { id: 'episode-6', regimeId: 'regime-5', startOffsetRatio: 0.58, durationRatio: 0.12, label: 'Кратковременная нестабильность' },
      { id: 'episode-7', regimeId: 'regime-6', startOffsetRatio: 0.22, durationRatio: 0.16, label: 'Скачок частоты ЭЦН' }
    ]
  }

  return createEpisodesInsideRegimes(data, regimes, episodesByScenario[scenario])
}

function buildDailyCauses(data: TimeSeriesPoint[], regimes: EventInterval[], episodes: EventInterval[]): DailyCauseBand[] {
  const fallbackDailyCause = { label: 'стабильная работа', color: '#6b7c93' }

  return data.map((point) => {
    const activeRegime = regimes.find((interval) => interval.startDate <= point.date && point.date <= interval.endDate)
    const activeEpisode = episodes.find((interval) => interval.startDate <= point.date && point.date <= interval.endDate)

    const causeItem =
      (activeEpisode && dailyCauseByEpisode.get(activeEpisode.label)) ||
      (activeRegime && dailyCauseByRegime.get(activeRegime.label)) ||
      fallbackDailyCause

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
        comment: 'Контроль стабилизации после вывода скважины на рабочий режим.'
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
        comment: 'ОПЗ проведена в попытке поддержать дебит до начала устойчивого роста воды.'
      },
      {
        ratio: 0.38,
        operationType: 'освоение после ОПЗ',
        comment: 'Кратковременный эффект после вмешательства и переход к новому режиму.'
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
        comment: 'Контрольная промывка ЭЦН перед повторной стабилизацией режима.'
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
      modelEventIntervals: [],
      modelRootCauseIntervals: []
    }
  }

  const scenario = detectScenario(data)
  const modelRootCauseIntervals = createScenarioRegimes(data, scenario)
  const modelEventIntervals = createScenarioEpisodes(data, scenario, modelRootCauseIntervals)
  const dailyCauses = buildDailyCauses(data, modelRootCauseIntervals, modelEventIntervals)
  const installedEspPeriods = buildInstalledEspPeriods(data, scenario)
  const opzEvents = buildOpzEvents(data, scenario)
  const espWashEvents = buildEspWashEvents(data, scenario)

  return {
    installedEspPeriods,
    dailyCauses,
    opzEvents,
    espWashEvents,
    modelEventIntervals,
    modelRootCauseIntervals
  }
}
