import axios, { type InternalAxiosRequestConfig } from 'axios';
import { ApiError, canRefresh, getCsrfToken, isMutation, refreshSession, sessionExpired, sessionVersion, sessionEpoch, assertSessionEpoch, isCsrfMismatch, invalidateCsrfToken } from '../lib/session';
import { API_BASE_URL } from '../lib/api';

/** UUIDs and ISO 8601 dates are serialized as strings by the backend. */
export interface AdminCandidate {
  id: string;
  election_id: string;
  name: string;
  description: string | null;
}

export interface AdminElection {
  id: string;
  title: string;
  description: string | null;
  status: 'draft' | 'active' | 'closed';
  starts_at: string;
  ends_at: string;
  created_by: string;
  closed_at: string | null;
  results_published: boolean;
  results_published_at: string | null;
  candidates: AdminCandidate[];
}

export interface ElectionTurnout {
  election_id: string;
  eligible_count: number;
  participants_count: number;
  turnout_percent: number;
  consistent: boolean;
}

export interface CandidateResult {
  candidate_id: string;
  name: string;
  votes_count: number;
  percent: number;
}

export interface AdminElectionResults extends ElectionTurnout {
  title: string;
  total_votes: number;
  outcome: 'no_votes' | 'winner' | 'tie';
  winner_ids: string[];
  closed_at: string | null;
  results: CandidateResult[];
  results_published: boolean;
}

export interface AuditEntry {
  id: string;
  election_id: string | null;
  actor_user_id: string | null;
  action: string;
  details: Record<string, unknown>;
  created_at: string;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true, 
  headers: {
    'Content-Type': 'application/json',
  },
});

// Both API clients share CSRF retrieval and a single in-flight refresh.
type SessionConfig = InternalAxiosRequestConfig & { sessionRetry?: boolean; sessionVersion?: number; sessionEpoch?: number; csrfRetry?: boolean };
api.interceptors.request.use(async (config: SessionConfig) => {
  config.sessionEpoch ??= sessionEpoch();
  assertSessionEpoch(config.sessionEpoch);
  config.sessionVersion = sessionVersion();
  try {
    if (isMutation(config.method)) config.headers.set('X-CSRF-Token', await getCsrfToken());
  } catch (error) {
    assertSessionEpoch(config.sessionEpoch);
    if (error instanceof ApiError && error.status === 401) sessionExpired();
    throw error;
  }
  assertSessionEpoch(config.sessionEpoch);
  return config;
});
api.interceptors.response.use(response => {
  assertSessionEpoch((response.config as SessionConfig).sessionEpoch ?? sessionEpoch());
  return response;
}, async (error: unknown) => {
  if (!axios.isAxiosError(error) || !error.config) throw error;
  const config = error.config as SessionConfig;
  assertSessionEpoch(config.sessionEpoch ?? sessionEpoch());
  if (isMutation(config.method) && !config.csrfRetry && isCsrfMismatch(error.response?.status ?? 0, error.response?.data)) {
    config.csrfRetry = true;
    invalidateCsrfToken(String(config.headers.get('X-CSRF-Token') || '') || null);
    return api.request(config);
  }
  if (error.response?.status !== 401) throw error;
  if (config.sessionRetry || !canRefresh(config.url || '')) {
    sessionExpired();
    throw error;
  }
  config.sessionRetry = true;
  await refreshSession(config.sessionVersion ?? sessionVersion());
  assertSessionEpoch(config.sessionEpoch ?? sessionEpoch());
  return api.request(config);
});

export const adminApi = {
  createElection: async (data: {
    title: string;
    description?: string;
    starts_at: string;
    ends_at: string;
    candidates?: Array<{ name: string; description?: string }>;
  }) => {
    const response = await api.post('/admin/elections', data);
    return response.data;
  },

  getElections: async () => {
    const response = await api.get<AdminElection[]>('/admin/elections');
    return response.data;
  },

  getElectionDetail: async (electionId: string) => {
    const response = await api.get<AdminElection>(`/admin/elections/${electionId}`);
    return response.data;
  },

  updateElection: async (electionId: string, data: {
    title?: string;
    description?: string;
    starts_at?: string;
    ends_at?: string;
  }) => {
    const response = await api.patch(`/admin/elections/${electionId}`, data);
    return response.data;
  },

  deleteElection: async (electionId: string) => {
    const response = await api.delete(`/admin/elections/${electionId}`);
    return response.status === 204;
  },

  addCandidate: async (electionId: string, data: { name: string; description?: string }) => {
    const response = await api.post(`/admin/elections/${electionId}/candidates`, data);
    return response.data;
  },

  removeCandidate: async (electionId: string, candidateId: string) => {
    const response = await api.delete(`/admin/elections/${electionId}/candidates/${candidateId}`);
    return response.status === 204;
  },

  getVoters: async (electionId: string) => {
    const voters: { id: string; email: string }[] = [];
    for (let offset = 0; ; offset += 1000) {
      const response = await api.get<{ id: string; email: string }[]>(`/admin/elections/${electionId}/voters`, {
        params: { limit: 1000, offset },
      });
      voters.push(...response.data);
      if (response.data.length < 1000) return voters;
    }
  },

  addVotersBatch: async (electionId: string, emails: string[]) => {
    const response = await api.post(`/admin/elections/${electionId}/voters`, { emails });
    return response.data;
  },

  removeVoter: async (electionId: string, voterId: string) => {
    const response = await api.delete(`/admin/elections/${electionId}/voters/${voterId}`);
    return response.status === 204;
  },

  activateElection: async (electionId: string) => {
    const response = await api.post(`/admin/elections/${electionId}/activate`);
    return response.data;
  },

  closeElection: async (electionId: string) => {
    const response = await api.post(`/admin/elections/${electionId}/close`);
    return response.data;
  },

  publishResults: async (electionId: string) => {
    const response = await api.post(`/admin/elections/${electionId}/results/publish`);
    return response.data;
  },

  unpublishResults: async (electionId: string) => {
    const response = await api.post(`/admin/elections/${electionId}/results/unpublish`);
    return response.data;
  },

  getTurnout: async (electionId: string) => {
    const response = await api.get<ElectionTurnout>(`/admin/elections/${electionId}/turnout`);
    return response.data;
  },

  getAdminResults: async (electionId: string) => {
    const response = await api.get<AdminElectionResults>(`/admin/elections/${electionId}/results`);
    return response.data;
  },

  exportResults: async (electionId: string) => {
    const response = await api.get<Blob>(`/admin/elections/${electionId}/results/export.csv`, {
      responseType: 'blob',
    });
    return response.data;
  },

  getAuditLog: async (electionId: string, offset = 0) => {
    const response = await api.get<AuditEntry[]>(`/admin/elections/${electionId}/audit`, {
      params: { offset, limit: 100 },
    });
    return response.data;
  },

  checkIntegrity: async (electionId: string) => {
    const response = await api.get(`/admin/elections/${electionId}/integrity`);
    return response.data;
  }
};