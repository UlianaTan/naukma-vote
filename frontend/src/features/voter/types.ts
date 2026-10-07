export interface User {
  id: string;
  email: string;
  name: string;
  role: "voter" | "organizer";
}

export type ElectionStatus = "draft" | "active" | "closed";

export interface Candidate {
  id: string;
  name: string;
  description: string;
}

export interface Election {
  id: string;
  title: string;
  description: string;
  status: ElectionStatus;
  startsAt: string;
  endsAt: string;
  candidates: Candidate[];
}

export interface SubmitVoteResponse {
  success: boolean;
  votedAt: string;
}
