import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { ClipboardList, X } from 'lucide-react';
import type { KanbanList, Label, PendingEntry } from '../../types';
import { apiJson } from '../../lib/api';
import { MOTION_EASE } from '../motion/motionTokens';
import { MorphButton, type MorphButtonState } from '../fluid/morph-button/MorphButton';

interface NewOsModalProps {
  open: boolean;
  lists: KanbanList[];
  labels: Label[];
  initialEntry?: PendingEntry | null;
  onClose: () => void;
  onCreated: (osNumber: string) => void;
}

interface ClientSuggestion {
  client_name: string;
  trade_name?: string;
  cnpj_cpf?: string;
  phone?: string;
  email?: string;
  address?: string;
  city_state?: string;
}

interface ScaleSuggestion {
  model_name: string;
  brand?: string;
  equipment_type?: string;
  capacity?: string;
}

export const NewOsModal: React.FC<NewOsModalProps> = ({
  open,
  lists,
  labels,
  initialEntry = null,
  onClose,
  onCreated,
}) => {
  const [osNumber, setOsNumber] = useState('');
  const [clientName, setClientName] = useState('');
  const [cnpjCpf, setCnpjCpf] = useState('');
  const [tradeName, setTradeName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [address, setAddress] = useState('');
  const [cityState, setCityState] = useState('');
  const [accessoriesJson, setAccessoriesJson] = useState('[]');
  const [equipmentType, setEquipmentType] = useState('Balança Toledo Prix');
  const [equipmentModel, setEquipmentModel] = useState('');
  const [serialNumber, setSerialNumber] = useState('');
  const [reportedDefect, setReportedDefect] = useState('');
  const [previousService, setPreviousService] = useState('');
  const [listId, setListId] = useState<string>('');
  const [selectedLabels, setSelectedLabels] = useState<Label[]>([]);
  const [files, setFiles] = useState<FileList | null>(null);
  const [clientSuggestions, setClientSuggestions] = useState<ClientSuggestion[]>([]);
  const [scaleSuggestions, setScaleSuggestions] = useState<ScaleSuggestion[]>([]);
  const [btnState, setBtnState] = useState<MorphButtonState>('idle');
  const [error, setError] = useState('');
  const [linkedEntryId, setLinkedEntryId] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;
    setError('');
    setBtnState('idle');
    const orcCol = lists.find((l) => l.role === 'orcamento' || l.title.toUpperCase() === 'ORÇAMENTOS') || lists[0];
    const defaultListId = orcCol ? String(orcCol.id) : '';
    resetForm(defaultListId);
    if (initialEntry) {
      setLinkedEntryId(initialEntry.id);
      setClientName(initialEntry.client_name || '');
      setCnpjCpf(initialEntry.cnpj_cpf || '');
      setTradeName(initialEntry.trade_name || '');
      setPhone(initialEntry.phone || '');
      setEmail(initialEntry.email || '');
      setAddress(initialEntry.address || '');
      setCityState(initialEntry.city_state || '');
      setAccessoriesJson(initialEntry.accessories_json || '[]');
      setEquipmentType(initialEntry.equipment_type || 'Balança Toledo Prix');
      setEquipmentModel(initialEntry.equipment_model || '');
      setSerialNumber(initialEntry.serial_number || '');
      setReportedDefect(initialEntry.reported_defect || '');
      setPreviousService(initialEntry.previous_service || '');
    }
  }, [open, initialEntry]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const resetForm = (defaultListId: string) => {
    setOsNumber('');
    setClientName('');
    setCnpjCpf('');
    setTradeName('');
    setPhone('');
    setEmail('');
    setAddress('');
    setCityState('');
    setAccessoriesJson('[]');
    setEquipmentType('Balança Toledo Prix');
    setEquipmentModel('');
    setSerialNumber('');
    setReportedDefect('');
    setPreviousService('');
    setListId(defaultListId);
    setSelectedLabels([]);
    setFiles(null);
    setClientSuggestions([]);
    setScaleSuggestions([]);
    setLinkedEntryId(null);
  };

  const handleClientInput = async (val: string) => {
    setClientName(val);
    if (val.trim().length < 2) {
      setClientSuggestions([]);
      return;
    }
    const res = await apiJson<{ clients: ClientSuggestion[] }>(`/api/clients/search?q=${encodeURIComponent(val)}`);
    if (res.ok) setClientSuggestions(res.data.clients || []);
  };

  const handleModelInput = async (val: string) => {
    setEquipmentModel(val);
    if (val.trim().length < 2) {
      setScaleSuggestions([]);
      return;
    }
    const res = await apiJson<{ scales: ScaleSuggestion[] }>(`/api/scales/search?q=${encodeURIComponent(val)}`);
    if (res.ok) setScaleSuggestions(res.data.scales || []);
  };

  const appendDefect = (txt: string) => {
    setReportedDefect((prev) => {
      const clean = prev.trim();
      if (!clean) return txt;
      if (clean.toLowerCase().includes(txt.toLowerCase())) return prev;
      return `${clean}, ${txt}`;
    });
  };

  const toggleLabel = (lbl: Label) => {
    setSelectedLabels((prev) =>
      prev.some((x) => x.name.toUpperCase() === lbl.name.toUpperCase())
        ? prev.filter((x) => x.name.toUpperCase() !== lbl.name.toUpperCase())
        : [...prev, lbl],
    );
  };

  const selectedCol = lists.find((l) => String(l.id) === listId);
  const isOrcCol =
    selectedCol?.role === 'orcamento' || (selectedCol?.title || '').toUpperCase().includes('ORÇAMENTO');

  const availableLabels = isOrcCol
    ? labels.filter((l) => ['URGENTE', 'URGÊNCIA', 'EM GARANTIA'].includes(l.name.toUpperCase()))
    : labels;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBtnState('loading');

    const fd = new FormData();
    fd.append('os_number', osNumber.trim());
    fd.append('client_name', clientName.trim());
    fd.append('cnpj_cpf', cnpjCpf);
    fd.append('trade_name', tradeName);
    fd.append('phone', phone);
    fd.append('email', email);
    fd.append('address', address);
    fd.append('city_state', cityState);
    fd.append('accessories_json', accessoriesJson);
    fd.append('equipment_type', equipmentType);
    fd.append('equipment_model', equipmentModel);
    fd.append('serial_number', serialNumber);
    fd.append('reported_defect', reportedDefect);
    fd.append('previous_service', previousService);
    fd.append('list_id', listId);
    fd.append('labels_json', JSON.stringify(selectedLabels));
    if (linkedEntryId) {
      fd.append('pending_entry_id', String(linkedEntryId));
    }
    if (files) {
      Array.from(files).forEach((f) => fd.append('entry_photos', f));
    }

    const res = await apiJson<{ success: boolean; error?: string; card?: { os_number: string } }>('/api/cards', {
      method: 'POST',
      body: fd,
    });
    if (!res.ok || !res.data.success) {
      setBtnState('idle');
      setError(res.data.error || 'Erro ao criar O.S.');
      return;
    }

    setBtnState('done');
    const createdOs = res.data.card?.os_number || osNumber;
    setTimeout(() => {
      onCreated(createdOs);
      onClose();
    }, 650);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, scale: 0.94, y: 14 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="w-full max-w-2xl modernize-card p-6 max-h-[92vh] overflow-y-auto space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-500/15 text-blue-600 dark:text-sky-400 flex items-center justify-center">
                  <ClipboardList className="w-5 h-5" />
                </div>
                <h2 className="text-base font-extrabold text-zinc-900 dark:text-white">
                  Cadastrar Nova Ordem de Serviço
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fechar"
                className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-400 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {initialEntry && linkedEntryId && (
                <div className="p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-2">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="font-extrabold text-emerald-700 dark:text-emerald-300">
                      📸 Pré-entrada vinculada ({initialEntry.photos?.length || 0} foto(s) de {initialEntry.client_name})
                    </span>
                    <button
                      type="button"
                      onClick={() => setLinkedEntryId(null)}
                      className="text-[11px] font-bold text-rose-500 hover:underline cursor-pointer"
                    >
                      Desvincular
                    </button>
                  </div>
                  {initialEntry.photos?.length > 0 && (
                    <div className="flex gap-1.5 overflow-x-auto">
                      {initialEntry.photos.map((src, i) => (
                        <img key={i} src={src} alt="" className="w-11 h-11 rounded-lg object-cover border border-emerald-500/30" />
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Anexar fotos do equipamento (Opcional):
                </label>
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={(e) => setFiles(e.target.files)}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3.5 file:rounded-full file:border-0 file:text-xs file:font-bold file:bg-blue-500/15 file:text-blue-600 dark:file:text-sky-400 cursor-pointer border border-slate-200 dark:border-zinc-800 rounded-xl p-1.5 bg-white dark:bg-zinc-900"
                />
              </div>

              {/* O.S. & Cliente */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Nº O.S. (Teorema) *
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    required
                    value={osNumber}
                    onChange={(e) => setOsNumber(e.target.value)}
                    placeholder="Ex: 026901"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-mono font-bold text-sm focus:border-blue-500 focus:outline-none"
                  />
                </div>
                <div className="sm:col-span-2 relative">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Cliente / Empresa *
                  </label>
                  <input
                    type="text"
                    required
                    value={clientName}
                    onChange={(e) => handleClientInput(e.target.value)}
                    placeholder="Ex: PADARIA CENTRAL"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 uppercase text-xs font-bold focus:border-blue-500 focus:outline-none"
                  />
                  {clientSuggestions.length > 0 && (
                    <div className="absolute left-0 right-0 top-full mt-1 z-30 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl max-h-40 overflow-y-auto divide-y divide-slate-100 dark:divide-zinc-800">
                      {clientSuggestions.map((cs, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setClientName(cs.client_name);
                            setTradeName(cs.trade_name || '');
                            setCnpjCpf(cs.cnpj_cpf || '');
                            setPhone(cs.phone || '');
                            setEmail(cs.email || '');
                            setAddress(cs.address || '');
                            setCityState(cs.city_state || '');
                            setClientSuggestions([]);
                          }}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-blue-500/10 cursor-pointer"
                        >
                          <span className="font-bold block">{cs.client_name}</span>
                          {cs.trade_name && <span className="text-[10px] text-slate-500">{cs.trade_name}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Equipamento & Modelo */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Equipamento
                  </label>
                  <select
                    value={equipmentType}
                    onChange={(e) => setEquipmentType(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-semibold"
                  >
                    <option value="Balança Toledo Prix">Balança Toledo Prix</option>
                    <option value="Balança Comercial">Balança Comercial</option>
                    <option value="Balança Industrial / Plataforma">Balança Industrial</option>
                    <option value="Balança Analítica / Precisão">Balança Analítica</option>
                    <option value="Fatiador de Frios">Fatiador de Frios</option>
                    <option value="Relógio de Ponto">Relógio de Ponto</option>
                    <option value="Nobreak">Nobreak</option>
                  </select>
                </div>
                <div className="relative">
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Modelo / Carga
                  </label>
                  <input
                    type="text"
                    value={equipmentModel}
                    onChange={(e) => handleModelInput(e.target.value)}
                    placeholder="Ex: Prix 4 Uno / 32kg"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-semibold focus:border-blue-500 focus:outline-none"
                  />
                  {scaleSuggestions.length > 0 && (
                    <div className="absolute left-0 right-0 top-full mt-1 z-30 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 rounded-xl shadow-xl max-h-40 overflow-y-auto divide-y divide-slate-100 dark:divide-zinc-800">
                      {scaleSuggestions.map((sc, idx) => (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            setEquipmentModel(sc.model_name);
                            if (sc.equipment_type) setEquipmentType(sc.equipment_type);
                            setScaleSuggestions([]);
                          }}
                          className="w-full text-left px-3 py-2 text-xs hover:bg-blue-500/10 cursor-pointer"
                        >
                          <span className="font-bold">{sc.model_name}</span>
                          {sc.brand && <span className="text-[10px] text-slate-500 ml-1.5">({sc.brand})</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Série e Coluna Inicial */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Nº Série (Opcional)
                  </label>
                  <input
                    type="text"
                    value={serialNumber}
                    onChange={(e) => setSerialNumber(e.target.value)}
                    placeholder="Ex: SN-9988"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Coluna Inicial
                  </label>
                  <select
                    value={listId}
                    onChange={(e) => setListId(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
                  >
                    {lists.map((l) => (
                      <option key={l.id} value={l.id}>
                        {l.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Defeito */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Defeito Reclamado pelo Cliente
                </label>
                <input
                  type="text"
                  value={reportedDefect}
                  onChange={(e) => setReportedDefect(e.target.value)}
                  placeholder="Ex: Não liga, diferença de peso..."
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs"
                />
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {['Diferença de peso', 'Não liga', 'Falha no teclado', 'Impressor falhando'].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => appendDefect(d)}
                      className="px-2.5 py-1 rounded-full text-[10.5px] font-bold bg-slate-100 dark:bg-zinc-800 hover:bg-blue-600 hover:text-white transition cursor-pointer"
                    >
                      + {d}
                    </button>
                  ))}
                </div>
              </div>

              {/* Etiquetas Rápidas */}
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1.5">
                  Etiquetas Rápidas {isOrcCol && <span className="text-blue-500">(Orçamentos: Urgência / Garantia)</span>}
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {availableLabels.map((lbl) => {
                    const active = selectedLabels.some((s) => s.name.toUpperCase() === lbl.name.toUpperCase());
                    return (
                      <button
                        key={lbl.name}
                        type="button"
                        onClick={() => toggleLabel(lbl)}
                        className={`px-3 py-1 rounded-full text-[11px] font-bold border transition cursor-pointer ${
                          active
                            ? 'text-white shadow-sm ring-2 ring-blue-500/30'
                            : 'bg-white dark:bg-zinc-900 border-slate-300 dark:border-zinc-700 text-slate-600 dark:text-zinc-300'
                        }`}
                        style={active ? { backgroundColor: lbl.color, borderColor: lbl.color } : undefined}
                      >
                        {lbl.name} {active ? '✓' : '+'}
                      </button>
                    );
                  })}
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-bold">
                  {error}
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 cursor-pointer"
                >
                  Cancelar
                </button>
                <MorphButton
                  type="submit"
                  state={btnState}
                  labels={{ idle: 'Criar O.S.', loading: 'Criando...', done: 'O.S. Criada!' }}
                />
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
