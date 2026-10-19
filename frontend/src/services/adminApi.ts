import axios from 'axios';

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

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  withCredentials: true, 
  headers: {
    'Content-Type': 'application/json',
  },
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
    const response = await api.get(`/admin/elections/${electionId}/voters`);
    return response.data;
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

  getAuditLog: async (electionId: string) => {
    const response = await api.get(`/admin/elections/${electionId}/audit`);
    return response.data;
  },

  checkIntegrity: async (electionId: string) => {
    const response = await api.get(`/admin/elections/${electionId}/integrity`);
    return response.data;
  }
};