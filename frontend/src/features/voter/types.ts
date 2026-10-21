export interface User {
  id: string;
  email: string;
  role: "voter" | "admin";
  needs_password_setup: boolean;
}

export type ElectionStatus = "draft" | "active" | "closed";

export interface Candidate {
  id: string;
  election_id: string;
  name: string;
  description: string | null;
}

export interface Election {
  id: string;
  title: string;
  description: string | null;
  status: ElectionStatus;
  starts_at: string;
  ends_at: string;
  has_voted: boolean;
  results_published: boolean;
  closed_at: string | null;
  candidates: Candidate[];
}

export interface SubmitVoteResponse {
  status: "success";
  message: string;
}

export interface PublishedResults {
  election_id: string;
  title: string;
  total_votes: number;
  outcome: "winner" | "tie" | "no_votes";
  winner_ids: string[];
  closed_at: string | null;
  results: { candidate_id: string; name: string; votes_count: number; percent: number }[];
}
