import { renderReplayFrame } from './replayRenderer';
import type { Round, PlayerMovementPoint } from '@/types/domain';
import type { RoundKillEvent, RoundGrenadeEvent } from '@/api/index';

export interface RecordHighlightOptions {
  matchId: number;
  mapName: string;
  playersDetail: any[];
  highlight: {
    round_num: number;
    player: string;
    type: string;
    start_tick: number;
    end_tick: number;
  };
  roundDetail: Round;
  kills: RoundKillEvent[];
  grenades: RoundGrenadeEvent[];
  movements: PlayerMovementPoint[];
  mapImage: HTMLImageElement | null;
}

export function recordHighlightClip(opt: RecordHighlightOptions, onProgress?: (pct: number) => void): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const {
      mapName,
      playersDetail,
      highlight,
      roundDetail,
      kills,
      grenades,
      movements,
      mapImage,
    } = opt;

    const canvas = document.createElement('canvas');
    canvas.width = 1280;
    canvas.height = 720;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      reject(new Error('Failed to get 2D context'));
      return;
    }

    // Group movements by player
    const groupedMovements: Record<string, PlayerMovementPoint[]> = {};
    for (const pt of movements) {
      if (!groupedMovements[pt.player]) {
        groupedMovements[pt.player] = [];
      }
      groupedMovements[pt.player].push(pt);
    }
    for (const player in groupedMovements) {
      groupedMovements[player].sort((a, b) => a.tick - b.tick);
    }

    const stream = canvas.captureStream(30); // 30 FPS
    
    let mimeType = 'video/webm';
    if (MediaRecorder.isTypeSupported('video/webm;codecs=vp9')) {
      mimeType = 'video/webm;codecs=vp9';
    } else if (MediaRecorder.isTypeSupported('video/webm;codecs=vp8')) {
      mimeType = 'video/webm;codecs=vp8';
    }
    
    const chunks: Blob[] = [];
    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType });
    } catch (err) {
      console.warn('Failed to start MediaRecorder with preferred mimeType, falling back to default options', err);
      recorder = new MediaRecorder(stream);
    }

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        chunks.push(e.data);
      }
    };

    recorder.onstop = () => {
      const finalBlob = new Blob(chunks, { type: recorder.mimeType || mimeType });
      resolve(finalBlob);
    };

    recorder.onerror = (e) => {
      reject(e);
    };

    // Start tick & end tick with 3 second margins (64 tick/sec * 3 = 192 ticks)
    const margin = 192;
    const roundStartTick = roundDetail.freezeEndTick ?? roundDetail.startTick ?? 0;
    const roundEndTick = roundDetail.endTick ?? (roundStartTick + 2000);
    
    const rawStart = highlight.start_tick - margin;
    const rawEnd = highlight.end_tick + margin;
    
    const startTick = Math.max(roundStartTick, rawStart);
    const endTick = Math.min(roundEndTick, rawEnd);
    const totalTicksToRecord = endTick - startTick;

    if (totalTicksToRecord <= 0) {
      reject(new Error('Invalid highlight tick range'));
      return;
    }

    recorder.start();

    let currentAbsTick = startTick;
    const tickStep = 2.1333; // 64 ticks/sec at 30 fps (64 / 30 = 2.1333 ticks per frame)

    function drawNextFrame() {
      if (currentAbsTick > endTick) {
        recorder.stop();
        return;
      }

      const relativeTick = currentAbsTick - roundStartTick;

      renderReplayFrame({
        ctx: ctx!,
        width: canvas.width,
        height: canvas.height,
        round: roundDetail,
        currentTick: relativeTick,
        kills,
        grenades,
        groupedMovements,
        playersDetail,
        mapName,
        mapImage,
        mapImageLoaded: !!mapImage,
      });

      if (onProgress) {
        const progress = (currentAbsTick - startTick) / totalTicksToRecord;
        onProgress(Math.min(0.99, progress));
      }

      currentAbsTick += tickStep;
      requestAnimationFrame(drawNextFrame);
    }

    drawNextFrame();
  });
}
