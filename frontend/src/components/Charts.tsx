import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

export interface SeriesSpec {
  key: string
  name: string
  color: string
}

const TOOLTIP_STYLE = {
  backgroundColor: '#0d1623',
  border: '1px solid #1d2b3f',
  borderRadius: 8,
  fontFamily: 'JetBrains Mono, monospace',
  fontSize: 11,
  color: '#dce7f5',
}

export function MetricChart({
  data,
  series,
  height = 180,
  area = true,
  domain,
  xKey = 'day',
}: {
  data: Array<Record<string, number | string | undefined>>
  series: SeriesSpec[]
  height?: number
  area?: boolean
  domain?: [number | 'auto', number | 'auto']
  xKey?: string
}) {
  const Chart = area ? AreaChart : LineChart
  return (
    <ResponsiveContainer width="100%" height={height}>
      <Chart data={data} margin={{ top: 8, right: 10, left: -18, bottom: 0 }}>
        <defs>
          {series.map((item) => (
            <linearGradient key={item.key} id={`grad-${item.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={item.color} stopOpacity={0.3} />
              <stop offset="100%" stopColor={item.color} stopOpacity={0.015} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid stroke="#162234" strokeDasharray="2 4" vertical={false} />
        <XAxis dataKey={xKey} tickLine={false} axisLine={false} minTickGap={28} />
        <YAxis tickLine={false} axisLine={false} width={42} domain={domain} />
        <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#7f92a9' }} />
        {series.length > 1 && (
          <Legend wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono, monospace', color: '#7f92a9', paddingTop: 4 }} />
        )}
        {series.map((item) =>
          area ? (
            <Area
              key={item.key}
              type="monotone"
              dataKey={item.key}
              name={item.name}
              stroke={item.color}
              strokeWidth={1.6}
              fill={`url(#grad-${item.key})`}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ) : (
            <Line
              key={item.key}
              type="monotone"
              dataKey={item.key}
              name={item.name}
              stroke={item.color}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  )
}
