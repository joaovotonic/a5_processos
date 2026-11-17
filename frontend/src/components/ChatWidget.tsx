import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { MessageCircle, Send, X } from 'lucide-react';
import type { ChatMessage } from '../types';
import { apiJson, getSocket, playDoorbellSound } from '../lib/api';
import { MOTION_EASE, SPRING_SNAPPY } from './motion/motionTokens';

interface ChatWidgetProps {
  viewer: 'priscila' | 'jacson';
  onToast?: (msg: string) => void;
}

export const ChatWidget: React.FC<ChatWidgetProps> = ({ viewer, onToast }) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [unread, setUnread] = useState(0);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const openRef = useRef(open);
  openRef.current = open;

  const isJacson = viewer === 'jacson';
  const partnerName = isJacson ? 'Priscila (Recepção)' : 'Sr. Jacson (Diretoria)';
  const partnerShort = isJacson ? 'Priscila' : 'Sr. Jacson';

  const scrollBottom = () => {
    setTimeout(() => {
      if (listRef.current) {
        listRef.current.scrollTop = listRef.current.scrollHeight;
      }
    }, 40);
  };

  const markRead = async () => {
    try {
      await apiJson('/api/chat/read', {
        method: 'POST',
        body: JSON.stringify({ viewer }),
      });
      setUnread(0);
    } catch {
      // Ignore
    }
  };

  const loadMessages = async () => {
    const res = await apiJson<{
      success: boolean;
      messages: ChatMessage[];
      unread_for_jacson: number;
      unread_for_priscila: number;
    }>('/api/chat/messages');
    if (res.ok && res.data.success) {
      setMessages(res.data.messages || []);
      const count = isJacson ? res.data.unread_for_jacson : res.data.unread_for_priscila;
      setUnread(openRef.current ? 0 : count || 0);
      if (openRef.current) {
        scrollBottom();
      }
    }
  };

  useEffect(() => {
    loadMessages();
    const socket = getSocket();
    const onMsg = (msg: ChatMessage) => {
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
      if (msg.sender !== viewer) {
        playDoorbellSound();
        if (openRef.current) {
          markRead();
          scrollBottom();
        } else {
          setUnread((u) => u + 1);
          onToast?.(`💬 ${msg.sender_name}: ${msg.message.slice(0, 60)}`);
        }
      } else {
        scrollBottom();
      }
    };
    socket.on('chat_message_received', onMsg);
    return () => {
      socket.off('chat_message_received', onMsg);
    };
  }, [viewer]);

  const handleToggle = () => {
    const next = !open;
    setOpen(next);
    if (next) {
      markRead();
      scrollBottom();
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    setSending(true);
    setDraft('');
    try {
      const res = await apiJson<{ success: boolean; message?: ChatMessage }>('/api/chat/messages', {
        method: 'POST',
        body: JSON.stringify({
          sender: viewer,
          sender_name: isJacson ? 'Sr. Jacson (Diretoria)' : 'Priscila (Recepção)',
          message: text,
        }),
      });
      if (res.ok && res.data.message) {
        setMessages((prev) => (prev.some((m) => m.id === res.data.message!.id) ? prev : [...prev, res.data.message!]));
        scrollBottom();
      }
    } finally {
      setSending(false);
    }
  };

  return (
    <div id={isJacson ? 'diretoriaChatWidget' : 'adminChatWidget'} className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 14, scale: 0.95 }}
            transition={SPRING_SNAPPY}
            className="w-[340px] sm:w-[370px] modernize-card overflow-hidden shadow-2xl border border-blue-500/25"
          >
            <div className="px-4 py-3 bg-gradient-to-r from-[#5D87FF] via-[#3B82F6] to-[#2563EB] text-white flex items-center justify-between">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center shrink-0">
                  <MessageCircle className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <h4 className="text-xs font-extrabold tracking-tight truncate">Chat Direto • {partnerName}</h4>
                  <p className="text-[10px] text-blue-100">Comunicação instantânea em tempo real</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleToggle}
                aria-label="Fechar chat"
                className="w-7 h-7 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center transition cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div
              ref={listRef}
              className="h-72 overflow-y-auto p-3 space-y-2 bg-[#F5F5F7] dark:bg-[#09090B]/90"
            >
              {messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-slate-400 dark:text-zinc-500 text-xs px-4">
                  <MessageCircle className="w-7 h-7 mb-2 opacity-40" />
                  <p className="font-semibold">Nenhuma mensagem ainda</p>
                  <p className="text-[11px] mt-0.5">Envie recados rápidos para {partnerName}.</p>
                </div>
              ) : (
                messages.map((m) => {
                  const mine = m.sender === viewer;
                  return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.18, ease: MOTION_EASE }}
                      className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}
                    >
                      <div
                        className={`max-w-[82%] rounded-2xl px-3.5 py-2 text-xs leading-relaxed shadow-xs ${
                          mine
                            ? 'bg-gradient-to-br from-[#3B82F6] to-[#2563EB] text-white rounded-br-sm'
                            : 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 border border-slate-200 dark:border-zinc-800 rounded-bl-sm'
                        }`}
                      >
                        <div className="font-medium break-words">{m.message}</div>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400 dark:text-zinc-500 mt-0.5 px-1">
                        {m.sender_name.split(' ')[0]} • {m.time_str}
                      </span>
                    </motion.div>
                  );
                })
              )}
            </div>

            <form onSubmit={handleSend} className="p-2.5 bg-white dark:bg-zinc-950 border-t border-slate-200 dark:border-zinc-800 flex items-center gap-2">
              <input
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder={`Mensagem para ${partnerShort}...`}
                className="flex-1 px-3.5 py-2 rounded-full text-xs bg-slate-100 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 border border-transparent focus:border-blue-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                aria-label="Enviar mensagem"
                className="w-9 h-9 rounded-full btn-modernize-primary flex items-center justify-center disabled:opacity-50 cursor-pointer shrink-0"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={handleToggle}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.96 }}
        className="relative inline-flex items-center gap-2 px-4 py-2.5 rounded-full btn-modernize-primary text-xs shadow-xl cursor-pointer"
      >
        <MessageCircle className="w-4 h-4" />
        <span>Chat • {partnerShort}</span>
        {unread > 0 && (
          <span className="ml-0.5 px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-black tabular-nums animate-pulse">
            {unread}
          </span>
        )}
      </motion.button>
    </div>
  );
};
