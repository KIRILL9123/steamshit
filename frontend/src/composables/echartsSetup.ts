/**
 * One-time ECharts setup. Imported by every chart component so that
 * `VChart` from `vue-echarts` has the necessary renderers and
 * components registered. Tree-shaken to keep the bundle small —
 * only the chart types we actually use (line, bar, radar) are
 * pulled in.
 */
import { use } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { BarChart, LineChart, RadarChart } from 'echarts/charts';
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';

let registered = false;

export function ensureEChartsRegistered(): void {
  if (registered) return;
  use([
    CanvasRenderer,
    BarChart,
    LineChart,
    RadarChart,
    DatasetComponent,
    GridComponent,
    LegendComponent,
    RadarComponent,
    TitleComponent,
    TooltipComponent,
  ]);
  registered = true;
}
