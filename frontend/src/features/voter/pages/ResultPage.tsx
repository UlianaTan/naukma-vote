import { Link, useParams } from "react-router-dom";
import { useElection } from "../hooks/useElection";

export function ResultPage() {
  const { id } = useParams<{ id: string }>();
  const { election, isLoading } = useElection(id);

  if (isLoading) {
    return <div className="max-w-xl mx-auto px-4 py-8 text-center text-muted-foreground">Завантаження...</div>;
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-12 text-center space-y-4">
      <div className="text-4xl">✅</div>
      <h1 className="text-xl font-semibold">Ваш голос враховано</h1>
      {election && (
        <p className="text-muted-foreground">
          Дякуємо за участь у голосуванні «{election.title}»
        </p>
      )}
      <Link
        to="/"
        className="inline-block mt-4 bg-primary text-primary-foreground rounded-md px-5 py-2.5 font-medium"
      >
        До списку голосувань
      </Link>
    </div>
  );
}
