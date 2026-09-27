import type { Election } from "../types";

export const mockElections: Election[] = [
  {
    id: "1",
    title: "Вибори старости групи ФІ-21",
    description: "Обрання старости на 2026/2027 навчальний рік",
    status: "active",
    startsAt: "2026-09-25T09:00:00Z",
    endsAt: "2026-09-30T20:00:00Z",
  },
  {
    id: "2",
    title: "Вибори голови студради",
    description: "Щорічне обрання голови студентської ради",
    status: "active",
    startsAt: "2026-09-20T09:00:00Z",
    endsAt: "2026-09-27T20:00:00Z",
  },
];
