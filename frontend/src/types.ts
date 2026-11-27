export type UserRole = 'master' | 'admin_recepcao' | 'diretoria';

export interface AuthUser {
  id?: number;
  username: string;
  display_name: string;
  role: UserRole;
  home_route: string;
}

export interface CallTarget {
  name: string;
  role: 'Técnico' | 'ADM';
  target: string;
}

export interface DefaultPasswordUser {
  username: string;
  display_name: string;
  role: UserRole;
}

export interface SystemUpdateCommit {
  hash: string;
  message: string;
  author: string;
  date: string;
  is_backup?: boolean;
}

export interface SystemUpdateStatus {
  success: boolean;
  has_update: boolean;
  behind_count: number;
  branch: string;
  repo: string;
  current_commit?: string;
  current_message?: string;
  remote_commit?: string;
  commits: SystemUpdateCommit[];
  applying?: boolean;
  checked_at?: string;
  error?: string;
}

export interface A5BootConfig {
  publicUrl?: string;
  localIp: string;
  port: number;
  tunnelMode: boolean;
  user: AuthUser | null;
  directorFirstAccessDone: boolean;
  directorSavedUser: string;
  usingDefaultPassword?: boolean;
  defaultPasswordUsers?: DefaultPasswordUser[];
  callTargets: CallTarget[];
  page?: string;
}

export interface Label {
  id?: number;
  name: string;
  color: string;
  text_color?: string;
  priority?: number;
}

export interface QuoteData {
  weight_unit: 'kg' | 'g' | string;
  accessories: Record<string, string>;
  incoming_seal: { type: string; number: string };
  incoming_stamp: { type: string; number: string };
  contamination: string[];
  weights_initial: Record<string, string>;
  weights_final: Record<string, string>;
  technical_report: string;
  solution: string;
  parts_items: Array<{ qty: number; code: string; description: string }>;
  service_checks: Record<string, boolean>;
  functional_tests: Record<string, { status: string; note: string }>;
}

export interface KanbanCard {
  id: number;
  os_number: string;
  client_name: string;
  trade_name?: string;
  phone?: string;
  cnpj_cpf?: string;
  equipment_type: string;
  equipment_model: string;
  serial_number: string;
  shelf_location: string;
  reported_defect: string;
  previous_service: string;
  list_id: number;
  list_title?: string;
  list_role?: string;
  list_is_tech?: number;
  position: number;
  labels: Label[];
  entry_photos: string[];
  exit_photos: string[];
  label_before_photos: string[];
  label_after_photos: string[];
  quote_photos: string[];
  quote_status: string;
  quote_data: QuoteData;
  pipeline_phase?: string;
  evaluator_tech?: string;
  finisher_tech?: string;
  tech_name?: string;
  inicio_orcamento?: string;
  fim_orcamento?: string;
  inmetro_seal?: string;
  parts_used?: string;
  root_cause?: string;
  solution?: string;
  tech_notes?: string;
  admin_notes?: string;
  reopen_requested: number;
  reopen_requested_by: string;
  reopen_requested_at?: string | null;
  timer_end_at?: string | null;
  timer_label?: string;
  created_at: string;
  updated_at: string;
  moved_at: string;
  finished_at?: string | null;
  hours_in_stage: number;
  sla_expired: boolean;
  is_urgent: boolean;
  is_warranty: boolean;
  mobile_stage?: string;
  pop_calibration?: number;
  pop_cleaning?: number;
}

export interface KanbanList {
  id: number;
  title: string;
  position: number;
  is_tech: number;
  role: string;
  cards: KanbanCard[];
  card_count: number;
  total_card_count?: number;
  truncated?: boolean;
}

export interface PendingEntry {
  id: number;
  client_name: string;
  trade_name?: string;
  cnpj_cpf?: string;
  phone?: string;
  email?: string;
  address?: string;
  city_state?: string;
  equipment_type: string;
  equipment_model: string;
  serial_number: string;
  reported_defect: string;
  previous_service: string;
  accessories_json?: string;
  photos: string[];
  created_at: string;
}

export interface BoardData {
  lists: KanbanList[];
  labels: Label[];
  settings: Record<string, string>;
  pending_entries: PendingEntry[];
  stats: {
    finished_today: number;
    tech_scores_today: Array<{ tech_name: string; count: number }>;
    total_active: number;
  };
}

export interface ExternalOrder {
  id: number;
  client_name: string;
  os_number: string;
  open_date: string;
  open_time: string;
  sector: string;
  equipment_model: string;
  reported_defect: string;
  tasks_notes: string;
  technician: string;
  route_date: string;
  route_shift: 'manha' | 'tarde' | string;
  route_order: number;
  status: string;
  attendance_status?: 'pending' | 'attended' | 'not_attended' | string;
  unattended_reason?: string;
}

export interface RouteSummary {
  status: string;
  route_date: string;
  route_shift: string;
  unassigned: ExternalOrder[];
  technicians: Record<string, ExternalOrder[]>;
}

export interface DirectorReport {
  kpis: {
    total_prontas: number;
    total_orcamentos_feitos: number;
    tempo_medio_orcamento_str: string;
    tempo_medio_manutencao_str: string;
    balancas_aguardando_cliente: number;
  };
  technicians_performance: Array<{
    name: string;
    orcamentos_count: number;
    prontas_count: number;
    tempo_medio_str: string;
    tempo_total_str: string;
  }>;
  os_details: Array<{
    os_number: string;
    client_name: string;
    equipment_model: string;
    tech_name: string;
    tempo_orcamento_str: string;
    tempo_manutencao_str: string;
    tempo_liquido_str: string;
    phase: string;
  }>;
}

export interface ChatMessage {
  id: number;
  sender: 'jacson' | 'priscila' | string;
  sender_name: string;
  message: string;
  is_read: number;
  created_at: string;
  time_str: string;
  date_str: string;
}
