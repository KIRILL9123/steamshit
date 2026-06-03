<script setup lang="ts">
/**
 * Thin wrapper over `lucide-vue-next`. Lets us change the icon set later
 * (or fall back to custom SVGs) without touching call sites.
 */
import { computed } from 'vue';
import {
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Crosshair,
  Database,
  Download,
  FileText,
  Filter,
  Flame,
  Gauge,
  Grid3X3,
  Info,
  Layers,
  LineChart,
  Loader,
  Map as MapIcon,
  Pause,
  Play,
  Plus,
  Save,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Target,
  Trash2,
  Upload,
  User,
  X,
  XCircle,
  XOctagon,
  Zap,
  type LucideIcon,
} from 'lucide-vue-next';

const props = withDefaults(
  defineProps<{ name: string; size?: number | string; stroke?: number }>(),
  { size: 16, stroke: 2 }
);

const map: Record<string, LucideIcon> = {
  'alert-triangle': AlertTriangle,
  'bar-chart-3': BarChart3,
  brain: Brain,
  'check-circle': CheckCircle,
  'chevron-down': ChevronDown,
  'chevron-right': ChevronRight,
  crosshair: Crosshair,
  database: Database,
  download: Download,
  'file-text': FileText,
  filter: Filter,
  flame: Flame,
  gauge: Gauge,
  'grid-3x3': Grid3X3,
  info: Info,
  layers: Layers,
  'line-chart': LineChart,
  loader: Loader,
  map: MapIcon,
  pause: Pause,
  play: Play,
  plus: Plus,
  save: Save,
  search: Search,
  settings: Settings,
  'shield-alert': ShieldAlert,
  sparkles: Sparkles,
  target: Target,
  trash: Trash2,
  upload: Upload,
  user: User,
  x: X,
  'x-circle': XCircle,
  'x-octagon': XOctagon,
  zap: Zap,
};

const component = computed(() => map[props.name] ?? Info);
</script>

<template>
  <component
    :is="component"
    :size="Number(size)"
    :stroke-width="stroke"
    aria-hidden="true"
  />
</template>
