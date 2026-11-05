<script setup lang="ts">
/**
 * Thin wrapper over `lucide-vue-next`. Lets us change the icon set later
 * (or fall back to custom SVGs) without touching call sites.
 */
import { computed } from 'vue';
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  Coins,
  Crosshair,
  Database,
  Download,
  FileText,
  Filter,
  Flame,
  Footprints,
  Gauge,
  Grid3X3,
  Info,
  Layers,
  Lightbulb,
  LineChart,
  Loader,
  Map as MapIcon,
  MapPin,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldAlert,
  ShieldCheck,
  SkipBack,
  Sparkles,
  Target,
  Trash2,
  TriangleAlert,
  Upload,
  User,
  X,
  XCircle,
  XOctagon,
  Zap,
  Video,
  type LucideIcon,
} from 'lucide-vue-next';

const props = withDefaults(
  defineProps<{ name: string; size?: number | string; stroke?: number }>(),
  { size: 16, stroke: 2 }
);

const map: Record<string, LucideIcon> = {
  'alert-triangle': AlertTriangle,
  'arrow-left-right': ArrowLeftRight,
  'arrow-right': ArrowRight,
  'bar-chart-3': BarChart3,
  brain: Brain,
  'check-circle': CheckCircle,
  'chevron-down': ChevronDown,
  'chevron-left': ChevronLeft,
  'chevron-right': ChevronRight,
  clock: Clock,
  coins: Coins,
  crosshair: Crosshair,
  database: Database,
  download: Download,
  'file-text': FileText,
  filter: Filter,
  flame: Flame,
  footprints: Footprints,
  gauge: Gauge,
  'grid-3x3': Grid3X3,
  info: Info,
  layers: Layers,
  lightbulb: Lightbulb,
  'line-chart': LineChart,
  loader: Loader,
  map: MapIcon,
  'map-pin': MapPin,
  pause: Pause,
  play: Play,
  plus: Plus,
  'refresh-cw': RefreshCw,
  save: Save,
  search: Search,
  settings: Settings,
  'shield-alert': ShieldAlert,
  'shield-check': ShieldCheck,
  'skip-back': SkipBack,
  sparkles: Sparkles,
  target: Target,
  trash: Trash2,
  'triangle-alert': TriangleAlert,
  upload: Upload,
  user: User,
  x: X,
  'x-circle': XCircle,
  'x-octagon': XOctagon,
  zap: Zap,
  video: Video,
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
