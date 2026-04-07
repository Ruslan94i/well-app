import type { HierarchicalEventTracks, TimeSeriesPoint } from '@/types/timeseries'

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

export function generateMockEventTracks(data: TimeSeriesPoint[]): HierarchicalEventTracks {
  if (data.length === 0) {
    return {
      installedEspPeriods: [],
      dailyCauses: [],
      opzEvents: []
    }
  }

  const lastIndex = data.length - 1

  const dailyCausePalette = [
    { label: 'stable', color: '#d9e2ec' },
    { label: 'esp', color: '#d7ccc8' },
    { label: 'water', color: '#c7d2fe' },
    { label: 'ops', color: '#cbd5e1' }
  ]

  const defaultCause = dailyCausePalette[0] ?? { label: 'stable', color: '#d9e2ec' }

  const dailyCauses = data.map((point, index) => {
    const colorItem = dailyCausePalette[Math.floor(index / 9) % dailyCausePalette.length] ?? defaultCause
    return {
      date: point.date,
      label: colorItem.label,
      color: colorItem.color
    }
  })

  const installedEspPeriods = [
    {
      id: 'esp-1',
      espId: 'ESP-A315',
      ...getRangeDates(data, 0, 66)
    },
    {
      id: 'esp-2',
      espId: 'ESP-B412',
      ...getRangeDates(data, 67, 126)
    },
    {
      id: 'esp-3',
      espId: 'ESP-C208',
      ...getRangeDates(data, 127, lastIndex)
    }
  ]

  const opzEvents = [
    {
      id: 'opz-1',
      date: data[22]?.date ?? data[0]?.date ?? '',
      operationType: 'acidizing',
      comment: 'Short productivity stimulation run.'
    },
    {
      id: 'opz-2',
      date: data[69]?.date ?? data[0]?.date ?? '',
      operationType: 'pump restart',
      comment: 'Restart after well intervention.'
    },
    {
      id: 'opz-3',
      date: data[132]?.date ?? data[lastIndex]?.date ?? '',
      operationType: 'perforation cleanup',
      comment: 'Post-cleanup stabilization period.'
    }
  ].filter((item) => item.date)

  return {
    installedEspPeriods,
    dailyCauses,
    opzEvents
  }
}
