import type { ExternalOrder } from '../types';
import { apiJson } from './api';

export interface ExportCompactRouteOptions {
  title: string;
  shiftLabel?: string;
  dateFormatted: string;
  techGroups: Array<[string, ExternalOrder[]]>;
  filename: string;
  action: 'copy' | 'download' | 'save';
  saveOnServer?: boolean;
  onToast?: (msg: string) => void;
}

function wrapCanvasText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
  font: string,
): string[] {
  ctx.font = font;
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const lines: string[] = [];
  let current = '';

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctx.measureText(candidate).width <= maxWidth) {
      current = candidate;
    } else {
      if (current) lines.push(current);
      if (ctx.measureText(word).width > maxWidth) {
        let part = '';
        for (const ch of word) {
          if (ctx.measureText(part + ch).width > maxWidth) {
            lines.push(part);
            part = ch;
          } else {
            part += ch;
          }
        }
        current = part;
      } else {
        current = word;
      }
    }
  }
  if (current) lines.push(current);
  return lines;
}

function drawRoundedRectPath(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
): void {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}

interface LayoutStop {
  seq: string;
  osLabel: string;
  clientLines: string[];
  metaLines: string[];
  defectLines: string[];
  noteLines: string[];
  height: number;
}

function renderRouteCanvas(opts: {
  title: string;
  shiftLabel?: string;
  dateFormatted: string;
  techGroups: Array<[string, ExternalOrder[]]>;
}): HTMLCanvasElement {
  const measureCtx = document.createElement('canvas').getContext('2d')!;
  const smallBoldFont = '700 11px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';
  const monoBoldFont = '800 12px "JetBrains Mono", Consolas, monospace';
  const clientFont = '800 14.5px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';
  const bodyFont = '600 12.5px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';
  const noteFont = '800 12.5px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';

  const shiftClean = (opts.shiftLabel || '').trim();
  const showShift = Boolean(shiftClean && shiftClean.toUpperCase() !== 'GERAL');
  const headerH = showShift ? 54 : 42;
  const sections: Array<{ techName: string; stops: LayoutStop[] }> = [];
  let totalHeight = headerH + 10;

  for (const [techName, orders] of opts.techGroups) {
    if (!orders || orders.length === 0) continue;
    totalHeight += 40;
    const stops: LayoutStop[] = [];
    orders.forEach((order, idx) => {
      const osLabel = order.os_number ? `OS ${order.os_number}` : 'S/N';
      const clientLines = wrapCanvasText(measureCtx, (order.client_name || '').toUpperCase(), 284, clientFont);
      const metaParts: string[] = [];
      if (order.sector) metaParts.push(`Setor: ${order.sector}`);
      if (order.equipment_model) metaParts.push(`Equip: ${order.equipment_model}`);
      const metaStr = metaParts.join(' • ');
      const metaLines = metaStr ? wrapCanvasText(measureCtx, metaStr, 392, bodyFont) : [];
      const defectLines = order.reported_defect
        ? wrapCanvasText(measureCtx, `Defeito: ${order.reported_defect}`, 392, bodyFont)
        : [];
      const noteLines = order.tasks_notes
        ? wrapCanvasText(measureCtx, `OBS: ${order.tasks_notes.toUpperCase()}`, 378, noteFont)
        : [];

      let h = 10;
      h += Math.max(24, clientLines.length * 18);
      if (metaLines.length > 0) h += 4 + metaLines.length * 16;
      if (defectLines.length > 0) h += 3 + defectLines.length * 16;
      if (noteLines.length > 0) h += 6 + noteLines.length * 16 + 10;
      h += 10;

      stops.push({
        seq: `${idx + 1}º`,
        osLabel,
        clientLines,
        metaLines,
        defectLines,
        noteLines,
        height: h,
      });
      totalHeight += h + 6;
    });
    totalHeight += 4;
    sections.push({ techName, stops });
  }

  totalHeight = Math.max(totalHeight + 8, 120);
  const canvas = document.createElement('canvas');
  canvas.width = 880;
  canvas.height = totalHeight * 2;
  const ctx = canvas.getContext('2d')!;
  ctx.scale(2, 2);
  ctx.textBaseline = 'top';

  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, 440, totalHeight);
  ctx.fillStyle = '#0F172A';
  ctx.fillRect(0, 0, 440, headerH);
  ctx.fillStyle = '#3B82F6';
  ctx.fillRect(0, headerH - 3, 440, 3);

  ctx.font = '800 13px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';
  ctx.fillStyle = '#FFFFFF';
  ctx.fillText(`A5 TECNOLOGIA • ${opts.title}`, 12, showShift ? 11 : 13);

  if (showShift) {
    ctx.font = smallBoldFont;
    ctx.fillStyle = '#38BDF8';
    ctx.fillText(`TURNO: ${shiftClean}`, 12, 31);
  }

  ctx.font = monoBoldFont;
  ctx.fillStyle = '#E2E8F0';
  const dateW = ctx.measureText(opts.dateFormatted).width;
  ctx.fillText(opts.dateFormatted, 428 - dateW, showShift ? 30 : 13);

  let y = headerH + 10;
  for (const sec of sections) {
    drawRoundedRectPath(ctx, 12, y, 416, 30, 8);
    ctx.fillStyle = '#1D4ED8';
    ctx.fill();
    ctx.font = '800 13px "Plus Jakarta Sans", "Segoe UI", Arial, sans-serif';
    ctx.fillStyle = '#FFFFFF';
    ctx.fillText(`TÉCNICO: ${sec.techName}`, 22, y + 8);

    const stopCountLabel = `${sec.stops.length} parada${sec.stops.length > 1 ? 's' : ''}`;
    ctx.font = smallBoldFont;
    ctx.fillStyle = '#DBEAFE';
    const countW = ctx.measureText(stopCountLabel).width;
    ctx.fillText(stopCountLabel, 418 - countW, y + 9);
    y += 36;

    sec.stops.forEach((st, idx) => {
      drawRoundedRectPath(ctx, 12, y, 416, st.height, 10);
      ctx.fillStyle = idx % 2 === 0 ? '#FFFFFF' : '#F8FAFC';
      ctx.fill();
      ctx.strokeStyle = '#CBD5E1';
      ctx.lineWidth = 1;
      ctx.stroke();

      let cy = y + 10;
      drawRoundedRectPath(ctx, 22, cy, 26, 22, 6);
      ctx.fillStyle = '#2563EB';
      ctx.fill();
      ctx.font = monoBoldFont;
      ctx.fillStyle = '#FFFFFF';
      const seqW = ctx.measureText(st.seq).width;
      ctx.fillText(st.seq, 22 + (26 - seqW) / 2, cy + 5);

      ctx.font = '800 11.5px "JetBrains Mono", Consolas, monospace';
      const badgeW = ctx.measureText(st.osLabel).width + 12;
      const badgeX = 418 - badgeW;
      drawRoundedRectPath(ctx, badgeX, cy, badgeW, 20, 6);
      ctx.fillStyle = '#EFF6FF';
      ctx.fill();
      ctx.strokeStyle = '#BFDBFE';
      ctx.stroke();
      ctx.fillStyle = '#1D4ED8';
      ctx.fillText(st.osLabel, badgeX + 6, cy + 4);

      ctx.font = clientFont;
      ctx.fillStyle = '#0F172A';
      st.clientLines.forEach((line, li) => {
        ctx.fillText(line, 54, cy + 2 + li * 18);
      });
      cy += Math.max(24, st.clientLines.length * 18);

      if (st.metaLines.length > 0) {
        cy += 4;
        ctx.font = bodyFont;
        ctx.fillStyle = '#334155';
        st.metaLines.forEach((line, li) => {
          ctx.fillText(line, 22, cy + li * 16);
        });
        cy += st.metaLines.length * 16;
      }

      if (st.defectLines.length > 0) {
        cy += 3;
        ctx.font = bodyFont;
        ctx.fillStyle = '#0F172A';
        st.defectLines.forEach((line, li) => {
          ctx.fillText(line, 22, cy + li * 16);
        });
        cy += st.defectLines.length * 16;
      }

      if (st.noteLines.length > 0) {
        cy += 6;
        const noteBoxH = st.noteLines.length * 16 + 10;
        drawRoundedRectPath(ctx, 22, cy, 392, noteBoxH, 6);
        ctx.fillStyle = '#FEF2F2';
        ctx.fill();
        ctx.strokeStyle = '#FCA5A5';
        ctx.stroke();
        ctx.font = noteFont;
        ctx.fillStyle = '#B91C1C';
        st.noteLines.forEach((line, li) => {
          ctx.fillText(line, 29, cy + 5 + li * 16);
        });
      }

      y += st.height + 6;
    });

    y += 4;
  }

  return canvas;
}

export async function exportCompactRoutePng(opts: ExportCompactRouteOptions): Promise<boolean> {
  const { title, shiftLabel = '', dateFormatted, techGroups, filename, action, saveOnServer = true, onToast } = opts;
  try {
    const canvas = renderRouteCanvas({ title, shiftLabel, dateFormatted, techGroups });
    const dataUrl = canvas.toDataURL('image/png');

    if (saveOnServer) {
      try {
        await apiJson('/api/externos/save-image', {
          method: 'POST',
          body: JSON.stringify({ image_base64: dataUrl, filename }),
        });
      } catch {
        // Ignore non-critical server archive failure
      }
    }

    if (action === 'download') {
      const a = document.createElement('a');
      a.download = filename;
      a.href = dataUrl;
      document.body.appendChild(a);
      a.click();
      a.remove();
      onToast?.(`📥 PNG compacto baixado (${filename})!`);
      return true;
    }

    if (action === 'copy') {
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'));
      if (!blob) throw new Error('Falha ao gerar imagem PNG.');
      try {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        onToast?.('📸 Imagem compacta copiada! Cole no WhatsApp com Ctrl+V.');
        return true;
      } catch {
        const a = document.createElement('a');
        a.download = filename;
        a.href = dataUrl;
        document.body.appendChild(a);
        a.click();
        a.remove();
        onToast?.(`📥 Clipboard bloqueado; PNG baixado automaticamente (${filename})!`);
        return true;
      }
    }

    return true;
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Erro ao gerar imagem PNG.';
    onToast?.(msg);
    return false;
  }
}

