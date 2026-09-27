export interface User {
  id: string;
  email: string;
  name: string;
  role: "voter" | "organizer";
}

export type ElectionStatus = "draft" | "active" | "closed";

export interface Election {
  id: string;
  title: string;
  description: string;
  status: ElectionStatus;
  startsAt: string;
  endsAt: string;
}
