// TODO: mock, замінити на реальний GET /api/elections коли Хомініч Катерина завершить endpoint
import type { Election } from "../types";

export const mockElections: Election[] = [
  {
    id: "1",
    title: "Вибори старости групи ФІ-21",
    description: "Обрання старости на 2026/2027 навчальний рік",
    status: "active",
    startsAt: "2026-09-25T09:00:00Z",
    endsAt: "2026-09-30T20:00:00Z",
    candidates: [
      { id: "c1", name: "Олена Ковальчук", description: "2 курс, досвід в оргкомітеті КВК" },
      { id: "c2", name: "Максим Руденко", description: "2 курс, голова наукового гуртка" },
    ],
  },
  {
    id: "2",
    title: "Вибори голови студради",
    description: "Щорічне обрання голови студентської ради",
    status: "active",
    startsAt: "2026-09-20T09:00:00Z",
    endsAt: "2026-09-27T20:00:00Z",
    candidates: [
      { id: "c3", name: "Ірина Бойко", description: "4 курс, діюча заступниця голови" },
      { id: "c4", name: "Дмитро Савчук", description: "3 курс, організатор студентських івентів" },
    ],
  },
];