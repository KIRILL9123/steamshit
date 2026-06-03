/**
 * Centralised ECharts theming. Values mirror `src/styles/tokens.css`
 * so the on-screen charts match the rest of the UI without a runtime
 * CSS-var roundtrip. If you change a token, update the matching
 * constant here too.
 */
export interface ChartColors {
  bg: string;
  bgElev: string;
  bgElev2: string;
  bgElev3: string;
  fg: string;
  fgMuted: string;
  fgDim: string;
  border: string;
  borderStrong: string;
  accent: string;
  info: string;
  success: string;
  warn: string;
  danger: string;
  ct: string;
  t: string;
  ctArea: string;
  tArea: string;
}

export function useChartColors(): ChartColors {
  return {
    bg: '#0E0F12',
    bgElev: '#16181E',
    bgElev2: '#1C1F26',
    bgElev3: '#242730',
    fg: '#E6E8F0',
    fgMuted: '#AAAFB9',
    fgDim: '#6E7382',
    border: '#2D313A',
    borderStrong: '#464C5A',
    accent: '#FF8C00',
    info: '#00C2FF',
    success: '#50C878',
    warn: '#F0B43C',
    danger: '#E64646',
    ct: '#5AA0E6',
    t: '#E6AF3C',
    ctArea: 'rgba(90, 160, 230, 0.18)',
    tArea: 'rgba(230, 175, 60, 0.18)',
  };
}

/**
 * ECharts `textStyle` block matching the typography tokens.
 */
export function useChartText(c: ChartColors) {
  return {
    fontFamily: "Inter, 'Segoe UI', system-ui, sans-serif",
    color: c.fgMuted,
  };
}
