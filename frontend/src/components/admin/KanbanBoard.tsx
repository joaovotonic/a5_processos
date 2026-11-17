import React, { memo, useCallback, useMemo, useRef, useState } from 'react';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  closestCorners,
  pointerWithin,
  useDroppable,
  useSensor,
  useSensors,
  type CollisionDetection,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
  type DropAnimation,
} from '@dnd-kit/core';
import { SortableContext, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Edit2, Plus, Trash2, Wrench } from 'lucide-react';
import type { KanbanCard, KanbanList } from '../../types';
import { KanbanCardItem } from './KanbanCardItem';

interface KanbanBoardProps {
  lists: KanbanList[];
  searchQuery: string;
  activeFilter: string;
  onMoveCard: (cardId: number, targetListId: number, newPosition: number, orderedCardIds: number[]) => void;
  onOpenDetail: (osNumber: string) => void;
  onAdvanceAdmin: (osNumber: string, action: string) => void;
  onDeleteRequest: (card: KanbanCard) => void;
  onCreateList: () => void;
  onRenameList: (list: KanbanList) => void;
  onDeleteList: (list: KanbanList) => void;
}

const LARGE_LIST_THRESHOLD = 60;
const INITIAL_VISIBLE_CARDS = 35;
const KANBAN_DROP_ANIMATION: DropAnimation = {
  duration: 180,
  easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
};

const DroppableColumnBody = memo<{
  list: KanbanList;
  visibleCards: KanbanCard[];
  totalFilteredCount: number;
  isLargeCapped: boolean;
  isExpanded: boolean;
  onToggleExpand: (listId: number) => void;
  onOpenDetail: (osNumber: string) => void;
  onAdvanceAdmin: (osNumber: string, action: string) => void;
  onDeleteRequest: (card: KanbanCard) => void;
}>(({
  list,
  visibleCards,
  totalFilteredCount,
  isLargeCapped,
  isExpanded,
  onToggleExpand,
  onOpenDetail,
  onAdvanceAdmin,
  onDeleteRequest,
}) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `col-${list.id}`,
    data: { type: 'column', listId: list.id },
  });
  const itemIds = useMemo(() => visibleCards.map((c) => `card-${c.id}`), [visibleCards]);
  const hiddenCount = Math.max(0, totalFilteredCount - visibleCards.length);

  return (
    <div
      ref={setNodeRef}
      className={`flex-1 overflow-y-auto p-2.5 space-y-2.5 min-h-[120px] transition-colors rounded-b-[20px] ${
        isOver ? 'bg-blue-500/8 dark:bg-sky-500/10' : ''
      }`}
    >
      <SortableContext items={itemIds} strategy={verticalListSortingStrategy}>
        {visibleCards.length === 0 ? (
          <div className="h-24 rounded-2xl border border-dashed border-slate-300/80 dark:border-zinc-800 flex items-center justify-center text-[11px] text-slate-400 dark:text-zinc-500 font-medium">
            Arraste cartões para cá
          </div>
        ) : (
          <>
            {isLargeCapped && isExpanded && (
              <button
                type="button"
                onClick={() => onToggleExpand(list.id)}
                className="w-full py-1.5 px-3 rounded-xl text-[11px] font-bold bg-slate-200/80 dark:bg-zinc-800 text-slate-700 dark:text-zinc-200 hover:bg-slate-300/80 transition cursor-pointer"
              >
                🔼 Mostrar apenas as {INITIAL_VISIBLE_CARDS} mais recentes
              </button>
            )}
            {visibleCards.map((card) => (
              <KanbanCardItem
                key={card.id}
                card={card}
                onOpenDetail={onOpenDetail}
                onAdvanceAdmin={onAdvanceAdmin}
                onDeleteRequest={onDeleteRequest}
              />
            ))}
            {isLargeCapped && !isExpanded && hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => onToggleExpand(list.id)}
                className="w-full py-2.5 px-3 rounded-xl text-[11px] font-extrabold bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-sky-400 border border-blue-500/30 transition cursor-pointer"
              >
                📂 Mostrar todas as {totalFilteredCount} O.S. (+{hiddenCount} anteriores)
              </button>
            )}
          </>
        )}
      </SortableContext>
    </div>
  );
});

const KanbanColumn = memo<{
  list: KanbanList;
  searchQuery: string;
  activeFilter: string;
  isExpanded: boolean;
  onToggleExpand: (listId: number) => void;
  onOpenDetail: (osNumber: string) => void;
  onAdvanceAdmin: (osNumber: string, action: string) => void;
  onDeleteRequest: (card: KanbanCard) => void;
  onRenameList: (list: KanbanList) => void;
  onDeleteList: (list: KanbanList) => void;
}>(({
  list,
  searchQuery,
  activeFilter,
  isExpanded,
  onToggleExpand,
  onOpenDetail,
  onAdvanceAdmin,
  onDeleteRequest,
  onRenameList,
  onDeleteList,
}) => {
  const { filteredCards, visibleCards, isLargeCapped } = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const filtered = list.cards.filter((c) => {
      if (q) {
        const hay = `${c.os_number} ${c.client_name} ${c.equipment_type} ${c.equipment_model} ${c.tech_name || ''} ${c.inmetro_seal || ''} ${c.reported_defect || ''} ${c.admin_notes || ''} ${(c.labels || []).map((l) => l.name).join(' ')}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      if (activeFilter === 'urgente' && !c.is_urgent) return false;
      if (activeFilter === 'sla' && !c.sla_expired) return false;
      if (activeFilter === 'estufa' && !c.timer_end_at) return false;
      if (activeFilter === 'reabrir' && c.reopen_requested !== 1) return false;
      return true;
    });

    const large = filtered.length > LARGE_LIST_THRESHOLD;
    if (!large || isExpanded) {
      return { filteredCards: filtered, visibleCards: filtered, isLargeCapped: large };
    }
    const isFinalCol =
      list.role === 'finalizada' || (list.title || '').toUpperCase().includes('FINALIZAD');
    const ordered = isFinalCol
      ? [...filtered].sort((a, b) => {
          const da = a.finished_at || a.moved_at || a.updated_at || a.created_at || '';
          const db = b.finished_at || b.moved_at || b.updated_at || b.created_at || '';
          return db > da ? 1 : db < da ? -1 : 0;
        })
      : filtered;
    return {
      filteredCards: filtered,
      visibleCards: ordered.slice(0, INITIAL_VISIBLE_CARDS),
      isLargeCapped: true,
    };
  }, [list.cards, list.role, list.title, searchQuery, activeFilter, isExpanded]);

  const isTech = Boolean(list.is_tech || list.title.toUpperCase().startsWith('TEC.'));

  return (
    <div
      data-no-pan
      className="w-[315px] shrink-0 max-h-[calc(100vh-175px)] flex flex-col rounded-[22px] bento-inner-tile shadow-sm overflow-hidden"
    >
      {/* Column Header */}
      <div className="px-3.5 py-3 bg-white/80 dark:bg-zinc-900/80 border-b border-slate-200/80 dark:border-zinc-800 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          {isTech && <Wrench className="w-3.5 h-3.5 text-blue-600 dark:text-sky-400 shrink-0" />}
          <h3 className="font-extrabold text-xs uppercase tracking-wider text-zinc-900 dark:text-zinc-100 truncate">
            {list.title}
          </h3>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span className="font-mono tabular-nums text-[11px] font-black px-2 py-0.5 rounded-full bg-blue-500/12 text-blue-600 dark:text-sky-400">
            {filteredCards.length}
          </span>
          <button
            type="button"
            onClick={() => onRenameList(list)}
            title="Renomear coluna"
            className="p-1 rounded-lg text-slate-400 hover:text-blue-600 dark:hover:text-sky-400 transition cursor-pointer"
          >
            <Edit2 className="w-3 h-3" />
          </button>
          {list.cards.length === 0 && (
            <button
              type="button"
              onClick={() => onDeleteList(list)}
              title="Excluir coluna vazia"
              className="p-1 rounded-lg text-slate-400 hover:text-rose-500 transition cursor-pointer"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          )}
        </div>
      </div>

      <DroppableColumnBody
        list={list}
        visibleCards={visibleCards}
        totalFilteredCount={filteredCards.length}
        isLargeCapped={isLargeCapped}
        isExpanded={isExpanded}
        onToggleExpand={onToggleExpand}
        onOpenDetail={onOpenDetail}
        onAdvanceAdmin={onAdvanceAdmin}
        onDeleteRequest={onDeleteRequest}
      />
    </div>
  );
});

export const KanbanBoard: React.FC<KanbanBoardProps> = ({
  lists,
  searchQuery,
  activeFilter,
  onMoveCard,
  onOpenDetail,
  onAdvanceAdmin,
  onDeleteRequest,
  onCreateList,
  onRenameList,
  onDeleteList,
}) => {
  const [activeCard, setActiveCard] = useState<KanbanCard | null>(null);
  const [localLists, setLocalLists] = useState<KanbanList[] | null>(null);
  const [expandedCols, setExpandedCols] = useState<Set<number>>(() => new Set());
  const canvasRef = useRef<HTMLDivElement>(null);
  const [isPanning, setIsPanning] = useState(false);
  const panState = useRef({ active: false, startX: 0, scrollLeft: 0 });
  const lastMovedCardToColRef = useRef<string>('');

  const displayLists = localLists ?? lists;
  const displayListsRef = useRef<KanbanList[]>(displayLists);
  displayListsRef.current = displayLists;

  const toggleExpandCol = useCallback((listId: number) => {
    setExpandedCols((prev) => {
      const next = new Set(prev);
      if (next.has(listId)) next.delete(listId);
      else next.add(listId);
      return next;
    });
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 4 },
    }),
  );

  // Detecção de colisão em 2 etapas com lista estável via ref (nunca recria callback no arraste):
  const kanbanCollisionDetection = useCallback<CollisionDetection>((args) => {
    const colContainers = args.droppableContainers.filter((c) => String(c.id).startsWith('col-'));
    const pointerCols = pointerWithin({ ...args, droppableContainers: colContainers });
    const targetColHits = pointerCols.length > 0 ? pointerCols : closestCenter({ ...args, droppableContainers: colContainers });

    if (targetColHits.length > 0) {
      const targetColIdStr = String(targetColHits[0].id);
      const listIdNum = Number(targetColIdStr.slice(4));
      const colData = displayListsRef.current.find((l) => l.id === listIdNum);
      if (colData) {
        const cardIdsInCol = new Set(colData.cards.map((c) => `card-${c.id}`));
        const scopedContainers = args.droppableContainers.filter((c) => cardIdsInCol.has(String(c.id)));
        const cardHits = closestCenter({ ...args, droppableContainers: scopedContainers });
        if (cardHits.length > 0) return cardHits;
        return targetColHits;
      }
    }
    return closestCorners(args);
  }, []);

  const findContainer = (id: string, sourceLists: KanbanList[]): number | null => {
    if (id.startsWith('col-')) return Number(id.slice(4));
    if (id.startsWith('card-')) {
      const cardId = Number(id.slice(5));
      for (const l of sourceLists) {
        if (l.cards.some((c) => c.id === cardId)) return l.id;
      }
    }
    return null;
  };

  const handleDragStart = (event: DragStartEvent) => {
    const card = event.active.data.current?.card as KanbanCard | undefined;
    lastMovedCardToColRef.current = '';
    if (card) {
      setActiveCard(card);
      // Reaproveita referências exatas das listas para preservar React.memo das colunas intocadas!
      setLocalLists(lists);
    }
  };

  const handleDragOver = (event: DragOverEvent) => {
    const { active, over } = event;
    if (!over || !localLists) return;

    const activeId = String(active.id);
    const overId = String(over.id);
    const activeColId = findContainer(activeId, localLists);
    const overColId = findContainer(overId, localLists);

    if (!activeColId || !overColId || activeColId === overColId) return;

    const moveSig = `${activeId}->${overColId}`;
    if (lastMovedCardToColRef.current === moveSig) return;
    lastMovedCardToColRef.current = moveSig;

    setLocalLists((prev) => {
      if (!prev) return prev;
      return prev.map((l) => {
        if (l.id === activeColId) {
          const cardId = Number(activeId.slice(5));
          return { ...l, cards: l.cards.filter((c) => c.id !== cardId) };
        }
        if (l.id === overColId) {
          const cardId = Number(activeId.slice(5));
          const moved = prev.find((src) => src.id === activeColId)?.cards.find((c) => c.id === cardId);
          if (!moved) return l;
          const nextCards = l.cards.filter((c) => c.id !== cardId);
          let newIdx = nextCards.length;
          if (overId.startsWith('card-')) {
            const overCardId = Number(overId.slice(5));
            const foundIdx = nextCards.findIndex((c) => c.id === overCardId);
            if (foundIdx >= 0) newIdx = foundIdx;
          }
          nextCards.splice(newIdx, 0, moved);
          return { ...l, cards: nextCards };
        }
        return l;
      });
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    const currentLists = localLists ?? lists;
    lastMovedCardToColRef.current = '';
    setActiveCard(null);

    if (!over) {
      setLocalLists(null);
      return;
    }

    const activeId = String(active.id);
    const overId = String(over.id);
    const activeColId = findContainer(activeId, currentLists);
    const overColId = findContainer(overId, currentLists);

    if (!activeColId || !overColId) {
      setLocalLists(null);
      return;
    }

    const next = currentLists.map((l) => ({ ...l, cards: [...l.cards] }));
    const targetList = next.find((l) => l.id === overColId);
    if (!targetList) {
      setLocalLists(null);
      return;
    }

    const cardId = Number(activeId.slice(5));
    if (activeColId === overColId && overId.startsWith('card-')) {
      const oldIdx = targetList.cards.findIndex((c) => c.id === cardId);
      const overCardId = Number(overId.slice(5));
      const newIdx = targetList.cards.findIndex((c) => c.id === overCardId);
      if (oldIdx >= 0 && newIdx >= 0 && oldIdx !== newIdx) {
        targetList.cards = arrayMove(targetList.cards, oldIdx, newIdx);
      }
    }

    const finalPos = targetList.cards.findIndex((c) => c.id === cardId);
    const orderedIds = targetList.cards.map((c) => c.id);

    // Atualiza otimisticamente o board no mesmo commit antes de limpar localLists (zero salto visual ao soltar)
    onMoveCard(cardId, targetList.id, Math.max(0, finalPos), orderedIds);
    setLocalLists(null);
  };

  // Drag-to-scroll on empty canvas background
  const onCanvasMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.closest('button, input, select, textarea, a, [data-no-pan]')) return;
    if (!target.classList.contains('kanban-pan-area')) return;
    if (!canvasRef.current) return;
    panState.current = {
      active: true,
      startX: e.pageX - canvasRef.current.offsetLeft,
      scrollLeft: canvasRef.current.scrollLeft,
    };
    setIsPanning(true);
  };

  const onCanvasMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!panState.current.active || !canvasRef.current) return;
    e.preventDefault();
    const x = e.pageX - canvasRef.current.offsetLeft;
    canvasRef.current.scrollLeft = panState.current.scrollLeft - (x - panState.current.startX);
  };

  const stopPan = () => {
    panState.current.active = false;
    setIsPanning(false);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={kanbanCollisionDetection}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={() => {
        lastMovedCardToColRef.current = '';
        setActiveCard(null);
        setLocalLists(null);
      }}
    >
      <div
        ref={canvasRef}
        onMouseDown={onCanvasMouseDown}
        onMouseMove={onCanvasMouseMove}
        onMouseUp={stopPan}
        onMouseLeave={stopPan}
        className={`kanban-pan-area kanban-canvas flex-1 overflow-x-auto overflow-y-hidden p-4 flex items-start gap-3.5 ${
          isPanning ? 'is-grabbing' : ''
        }`}
      >
        {displayLists.map((list) => (
          <KanbanColumn
            key={list.id}
            list={list}
            searchQuery={searchQuery}
            activeFilter={activeFilter}
            isExpanded={expandedCols.has(list.id)}
            onToggleExpand={toggleExpandCol}
            onOpenDetail={onOpenDetail}
            onAdvanceAdmin={onAdvanceAdmin}
            onDeleteRequest={onDeleteRequest}
            onRenameList={onRenameList}
            onDeleteList={onDeleteList}
          />
        ))}

        {/* Add List button */}
        <button
          type="button"
          onClick={onCreateList}
          className="w-64 shrink-0 py-4 px-4 rounded-[22px] border-2 border-dashed border-slate-300 dark:border-zinc-800 hover:border-blue-500 dark:hover:border-sky-400 text-slate-500 dark:text-zinc-400 hover:text-blue-600 dark:hover:text-sky-400 text-xs font-extrabold flex items-center justify-center gap-2 transition cursor-pointer bg-white/40 dark:bg-zinc-900/30"
        >
          <Plus className="w-4 h-4" />
          <span>Adicionar Coluna</span>
        </button>
      </div>

      <DragOverlay dropAnimation={KANBAN_DROP_ANIMATION}>
        {activeCard ? (
          <div className="w-[300px]">
            <KanbanCardItem
              card={activeCard}
              isOverlay
              onOpenDetail={() => {}}
              onAdvanceAdmin={() => {}}
              onDeleteRequest={() => {}}
            />
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
};
