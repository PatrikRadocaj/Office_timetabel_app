export type UserRole = "admin" | "agent" | string;

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  office_id?: string | null;
  is_active?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuthResponse {
  user: UserProfile;
  id_token: string;
  refresh_token: string;
  expires_in: number;
}

export interface Office {
  id: string;
  name: string;
  timezone: string;
  max_capacity: number;
  address?: string | null;
}

export interface Skill {
  id: string;
  name: string;
  min_proficiency: number;
  description?: string | null;
}

export interface AgentSkill {
  skill_id: string;
  proficiency: number;
}

export interface TimeWindow {
  day_of_week: number;
  start_hour: number;
  end_hour: number;
}

export interface Agent {
  id: string;
  full_name: string;
  email: string;
  office_id: string;
  weekly_max_hours: number;
  min_rest_hours: number;
  shift_preference: string;
  skills: AgentSkill[];
  availability?: TimeWindow[];
}

export interface Announcement {
  id: string;
  title: string;
  message: string;
  is_active: boolean;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export type DayOffRequestStatus = "pending" | "approved" | "rejected" | string;

export interface DayOffRequest {
  id: string;
  agent_id: string;
  user_id?: string | null;
  email?: string | null;
  full_name: string;
  office_id?: string | null;
  start_date: string;
  end_date: string;
  reason?: string | null;
  status: DayOffRequestStatus;
  requested_at: string;
  reviewed_at?: string | null;
  reviewed_by_user_id?: string | null;
  reviewed_by_name?: string | null;
  review_note?: string | null;
  schedule_impact: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export type ShiftSwapRequestStatus = "pending" | "approved" | "rejected" | string;

export interface ShiftSwapAssignmentRef {
  schedule_id: string;
  assignment_key: string;
}

export interface ShiftSwapOption {
  schedule_id: string;
  assignment_key: string;
  assignment_refs?: ShiftSwapAssignmentRef[];
  agent_id: string;
  agent_name: string;
  slot_start: string;
  slot_end: string;
  office_id: string;
  office_name: string;
  office_timezone?: string | null;
  skill_id: string;
  skill_name: string;
  skill_ids?: string[];
  skill_names?: string[];
}

export interface ShiftSwapOptionsResponse {
  my_shifts: ShiftSwapOption[];
  target_shifts: ShiftSwapOption[];
}

export interface ShiftSwapRequest {
  id: string;
  requester_agent_id: string;
  requester_user_id?: string | null;
  requester_name: string;
  requester_email?: string | null;
  target_agent_id: string;
  target_agent_name: string;
  target_agent_email?: string | null;
  source_schedule_id: string;
  source_assignment_key: string;
  target_schedule_id: string;
  target_assignment_key: string;
  source_assignment_refs?: ShiftSwapAssignmentRef[] | null;
  target_assignment_refs?: ShiftSwapAssignmentRef[] | null;
  source_shift: ShiftSwapOption;
  target_shift: ShiftSwapOption;
  reason?: string | null;
  status: ShiftSwapRequestStatus;
  requested_at: string;
  reviewed_at?: string | null;
  reviewed_by_user_id?: string | null;
  reviewed_by_name?: string | null;
  review_note?: string | null;
  schedule_impact: string;
  schedule_update?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DemandRow {
  id: string;
  office_id: string;
  skill_id: string;
  slot_start: string;
  slot_end: string;
  required_agents: number;
  priority: number;
  time_block?: string;
  forecast_date?: string;
}

export interface DayDemandBlock {
  block_start: string;
  slot_start: string;
  slot_end: string;
  totals_by_skill: Record<string, number>;
  total_required: number;
  coverage_by_skill: Record<string, number>;
  total_covered: number;
  coverage_gap: number;
  coverage_ratio: number;
}

export interface DemandDayView {
  office_id: string;
  date: string;
  interval_minutes: number;
  skill_ids: string[];
  blocks: DayDemandBlock[];
  coverage_schedule_id: string | null;
  coverage_generated_at: string | null;
}

export interface CoveragePoint {
  slot_start: string;
  office_id: string;
  skill_id: string;
  required: number;
  assigned: number;
  gap: number;
}

export interface DashboardSummary {
  total_agents: number;
  total_offices: number;
  total_skills: number;
  active_schedule_count: number;
  coverage_points: CoveragePoint[];
}

export interface ScheduleAssignment {
  slot_start: string;
  slot_end: string;
  office_id: string;
  skill_id: string;
  assigned_agent_ids: string[];
  required_agents: number;
  coverage_ratio: number;
  gap: number;
}

export interface ScheduleGenerationResponse {
  schedule_id: string;
  year?: number;
  week?: number;
  week_start?: string;
  week_end?: string;
  archived_schedule_ids?: string[];
  schedule_ids?: string[];
  document_count?: number;
  assignments: ScheduleAssignment[];
  total_required: number;
  total_assigned: number;
  uncovered_demand: number;
}

export interface AgentDayShift {
  date: string;
  day_name: string;
  shift_start: string | null;
  shift_end: string | null;
  office: string;
  required_skills: string[];
  total_hours: number;
  break_time?: string | null;
}

export interface AgentShiftListResponse {
  shifts: AgentDayShift[];
}

export interface AgentAvailabilityResponse {
  availability: TimeWindow[];
}

export interface AgentDashboardData {
  full_name: string;
  today_date: string;
  greeting: string;
  status_text: string;
  is_scheduled_today: boolean;
  today_shift?: {
    date: string;
    day_name: string;
    shift_start: string | null;
    shift_end: string | null;
    office: string;
    required_skills: string[];
    total_hours: number;
    break_time: string | null;
  } | null;
  weekly_schedule: AgentDayShift[];
  hours_overview: {
    weekly_max_hours: number;
    hours_worked_week: number;
    hours_remaining: number;
    overtime_hours: number;
  };
  skills: Array<{
    skill_id: string;
    skill_name: string;
    proficiency: number;
    proficiency_pct: number;
  }>;
  availability: TimeWindow[];
  announcements: Array<{
    id: string;
    title: string;
    message: string;
    published_at?: string | null;
  }>;
}
